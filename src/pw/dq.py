"""Data-quality scorecard.

    python -m pw.dq

Runs every check against the warehouse, then writes
    data/marts/dq_checks.csv              one row per check (also read by the dashboard)
    docs/data-quality-scorecard.md        the same, readable

Each check says what it measured, the number, and the rule it was held to. A check that fails its rule is not
hidden: the report leads with it. "info" means a measurement worth knowing that has no pass/fail rule.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import date

import duckdb

from .build import connect
from .sources import MARTS, RAW, ROOT

DOCS = ROOT / "docs"


@dataclass
class Check:
    id: str
    dimension: str
    name: str
    result: str
    rule: str
    status: str  # pass | warn | fail | info
    note: str


def _one(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()


def _pct(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None else f"{100 * x:.{digits}f}%"


def independent_ratio(con: duckdb.DuckDBPyConnection, as_of: date) -> float:
    """Weighted weekly index ratio for 'All', recomputed in Python from raw fact rows (no SQL window functions).

    sum(w * price) / sum(w * previous price) over packs priced this week and the week before, with w the pack's
    Medicaid units in that calendar year, leaving out relatives above 10x or below 0.1x.
    """
    rows = con.execute(
        """
        select f.ndc11, f.price, u.units
        from fact_nadac f join rx_units u on u.ndc11 = f.ndc11 and u.year = least(year(f.as_of), 2025)
        where f.as_of = ?""", [as_of]).fetchall()
    prev = dict(con.execute(
        "select ndc11, price from fact_nadac where as_of = (select max(as_of) from fact_nadac where as_of < ?)",
        [as_of]).fetchall())
    num = den = 0.0
    for ndc, price, units in rows:
        p0 = prev.get(ndc)
        if p0 is None or not units or units <= 0:
            continue
        rel = price / p0
        if rel > 10 or rel < 0.1:
            continue
        num += units * price
        den += units * p0
    return num / den


def run(con: duckdb.DuckDBPyConnection) -> list[Check]:
    checks: list[Check] = []
    add = checks.append
    expected = json.loads((RAW / "expected_rows.json").read_text())

    # ------------------------------------------------------------ completeness
    rows = dict(con.execute("select source_year, count(*) from stg_nadac group by 1").fetchall())
    bad = [y for y, n in rows.items() if expected.get(f"nadac_{y}") != n]
    add(Check("C01", "Completeness", "Rows loaded equal rows published, per year",
              f"{len(rows) - len(bad)} of {len(rows)} years match the count the portal reports",
              "every year equal", "pass" if not bad else "fail",
              f"{sum(rows.values()):,} rows, {min(rows)}-{max(rows)}."))
    gaps = dict(con.execute("""
        select gap, count(*) from (
          select date_diff('day', lag(d) over (order by d), d) as gap from (select distinct as_of as d from fact_nadac))
        where gap is not null group by 1""").fetchall())
    weeks = _one(con, "select count(distinct as_of) from fact_nadac")[0]
    off = sum(n for g, n in gaps.items() if g not in (6, 7, 8))
    add(Check("C02", "Completeness", "Weekly snapshots are consecutive",
              f"{weeks} snapshots; gaps in days: " + ", ".join(f"{g}d x{n}" for g, n in sorted(gaps.items())),
              "no gap longer than 8 days", "pass" if off == 0 else "fail",
              "A missing week would turn two weeks of price change into one 'weekly' move in the index."))

    # ------------------------------------------------------------ validity
    q_rows, q_reasons = _one(con, "select count(*), string_agg(distinct reason, '; ') from quarantine_nadac")
    add(Check("C03", "Validity", "Every row has a readable NDC, price, dates and rate-setting class",
              f"{q_rows:,} rows set aside" + (f" ({q_reasons})" if q_rows else ""),
              "0 rows set aside", "pass" if q_rows == 0 else "warn",
              "Rows that break a rule go to quarantine_nadac with the reason and never reach the facts. "
              "A first version of the rule threw away 2,885 'B-BIO' rows (a class NADAC added in 2022); "
              "reading them as a real class fixed it."))
    bad_price = _one(con, "select count(*) from fact_nadac where price <= 0 or price is null")[0]
    add(Check("C04", "Validity", "Prices are positive numbers", f"{bad_price:,} rows are not", "0",
              "pass" if bad_price == 0 else "fail", ""))
    units = dict(con.execute("select pricing_unit, count(*) from fact_nadac group by 1").fetchall())
    add(Check("C05", "Validity", "Pricing unit is one of EA (each), ML (millilitre) or GM (gram)",
              ", ".join(f"{k} {v:,}" for k, v in sorted(units.items())), "no other unit",
              "pass" if set(units) <= {"EA", "ML", "GM"} else "fail",
              "A price per tablet cannot be compared with a price per millilitre; each NDC keeps one unit."))
    dups = _one(con, "select count(*) from (select ndc11, as_of from fact_nadac group by 1, 2 having count(*) > 1)")[0]
    add(Check("C06", "Uniqueness", "One price per NDC per week", f"{dups:,} duplicated pairs", "0",
              "pass" if dups == 0 else "fail", ""))
    today = date.today()
    future = _one(con, f"select count(*) from fact_nadac where as_of > date '{today.isoformat()}'")[0]
    latest = _one(con, "select max(as_of) from fact_nadac")[0]
    add(Check("C07", "Timeliness", "Latest snapshot is recent and no snapshot is dated in the future",
              f"latest {latest.isoformat()} ({(today - latest).days} days old); {future} future-dated rows",
              "newest snapshot within 14 days; 0 future", "pass" if (today - latest).days <= 14 and future == 0 else "warn",
              "NADAC is republished weekly; the weekly job in .github/workflows re-checks this."))

    # ------------------------------------------------------------ consistency
    flips = _one(con, "select count(*) from (select ndc11 from fact_nadac group by 1 having count(distinct cls) > 1)")[0]
    total_ndc = _one(con, "select count(*) from dim_ndc")[0]
    add(Check("C08", "Consistency", "A pack keeps the same brand/generic class over time",
              f"{flips:,} of {total_ndc:,} packs change class at some point", "report", "info",
              "Usually a brand that lost exclusivity and was re-listed, or a reclassification. Each week's price is "
              "grouped by the class it had that week; the latest class is used for labels."))
    agree = con.execute("""
        select count(*) filter (where (segment = 'Generic') = (rx_market_class = 'Generic')),
               count(*)
        from dim_ndc where in_rx and rx_market_class in ('Brand', 'Generic')""").fetchone()
    add(Check("C09", "Consistency", "NADAC's class agrees with Rx Market Pulse's brand/generic flag",
              f"{_pct(agree[0] / agree[1])} of {agree[1]:,} packs agree", "report", "info",
              "They are different definitions: NADAC sets a rate class per drug; Rx Market Pulse uses the Medicaid "
              "product record. Examples that differ: unbranded insulin lispro (a biologic sold under the brand's "
              "licence) and eye-drop brands sold as unapproved generics. Brand/generic charts use NADAC's class; "
              "the molecule-level work (erosion) uses Rx Market Pulse's."))
    cov = con.execute("""
        select sum(u.units) filter (where d.ndc11 is not null) / sum(u.units),
               sum(u.spend) filter (where d.ndc11 is not null) / sum(u.spend)
        from rx_units u left join dim_ndc d on d.ndc11 = u.ndc11 where u.year = 2025""").fetchone()
    add(Check("C10", "Coverage", "How much of 2025 Medicaid volume has a NADAC price",
              f"{_pct(cov[0])} of units, {_pct(cov[1])} of spend", "report", "info",
              "NADAC prices what retail pharmacies buy, so clinic-administered and specialty products "
              "(Keytruda, most biologics) are absent. Spend coverage is far below unit coverage because those "
              "products are expensive."))
    in_rx = _one(con, "select count(*) filter (where in_rx), count(*) from dim_ndc")
    add(Check("C11", "Coverage", "NADAC packs that appear in the Medicaid product records",
              f"{_pct(in_rx[0] / in_rx[1])} of {in_rx[1]:,}", "report", "info",
              "Packs not in the records have no brand family, owner or therapeutic area, so they appear in the "
              "all-market and brand/generic indexes only."))

    # ------------------------------------------------------------ outliers and method
    n_ext = _one(con, "select count(*) from wk_rel where extreme")[0]
    n_rel = _one(con, "select count(*) from wk_rel")[0]
    add(Check("C12", "Outliers", "Week-on-week moves above 10x or below 0.1x",
              f"{n_ext:,} of {n_rel:,} comparisons ({_pct(n_ext / n_rel, 4)})", "left out of the indexes", "info",
              "Treated as data errors and excluded, in the numerator and the denominator alike."))
    with_rule = _one(con, """select weighted from mart_index_week where kind = 'segment' and grp = 'All'
                             order by as_of desc limit 1""")[0]
    no_rule = _one(con, """
        with r as (select as_of, sum(w * price) / sum(w * prev_price) as ratio from wk_rel where w > 0
                   and as_of >= date '2019-01-01' group by 1)
        select 100 * exp(sum(ln(ratio))) / exp(ln(first(ratio order by as_of))) from r""")[0]
    add(Check("C13", "Outliers", "The weighted all-market index barely depends on the outlier rule",
              f"latest value {with_rule:.1f} with the rule, {no_rule:.1f} without", "within 1 index point",
              "pass" if abs(with_rule - no_rule) <= 1 else "warn",
              "If dropping the rule moved the index a lot, the rule would be doing the work. It does not."))
    drift = con.execute("""
        select y, count(*) filter (where abs(pct) < 0.005) * 1.0 / count(*)
        from fact_change where segment = 'Brand' and y in (2022, 2024) group by y order by y""").fetchall()
    d = dict(drift)
    add(Check("C14", "Method break", "Brand rates start drifting by under 0.5% from 2024",
              f"share of brand changes under 0.5%: {_pct(d[2022])} in 2022, {_pct(d[2024])} in 2024",
              "report", "info",
              "A change in how NADAC is published, not a market event. Counts of 'changes' jump about five-fold; "
              "this project counts 'material' changes (1% or more) and says so wherever it counts."))
    bulk = con.execute("""
        select y, count(*) from (select year(as_of) y, as_of from fact_change group by 1, 2 having count(*) > 1000)
        where y between 2015 and 2025 group by y order by y""").fetchall()
    per_year = {y: n for y, n in bulk}
    add(Check("C15", "Method break", "Rates move in monthly bulk updates",
              "weeks with over 1,000 changes per year (2015-2025): "
              + ", ".join(f"{y}: {n}" for y, n in sorted(per_year.items())),
              "report", "info",
              "Published weekly, repriced monthly in practice. 'Latest movers' therefore means the latest bulk update."))

    # ------------------------------------------------------------ index health and independent recomputation
    thin = _one(con, """select count(*) from mart_index_week where kind = 'segment' and grp = 'All'
                        and as_of >= date '2019-01-02' and n_weighted < 5000""")[0]
    add(Check("C16", "Index health", "Every week since 2019 has at least 5,000 weighted packs in the all-market index",
              f"{thin} weeks below", "0", "pass" if thin == 0 else "warn", ""))
    sample = [date(2022, 3, 9), date(2024, 6, 19), date(2026, 9, 23)]
    worst = 0.0
    for wk in sample:
        sql_r = _one(con, f"select ratio_w from idx_week_ratio where kind = 'segment' and grp = 'All' "
                          f"and as_of = date '{wk.isoformat()}'")[0]
        worst = max(worst, abs(sql_r - independent_ratio(con, wk)))
    add(Check("C17", "Index health", "Weekly index ratio recomputed independently in Python",
              f"3 weeks checked; largest difference {worst:.2e}", "below 1e-9",
              "pass" if worst < 1e-9 else "fail",
              "Python re-derives the ratio from raw rows with no window functions, to catch a SQL mistake."))

    # ------------------------------------------------------------ analysis coverage
    n_ev = _one(con, "select count(*) from rx_events")[0]
    n_b, n_g = _one(con, """select count(distinct brand_family) filter (where side = 'brand'),
                                   count(distinct brand_family) filter (where side = 'generic')
                            from mart_erosion_price""")
    add(Check("C18", "Coverage", "Generic-entry events that NADAC can price",
              f"{n_b} of {n_ev} molecules have priced brand packs; {n_g} of {n_ev} have priced generic packs",
              "report", "info",
              "The rest are infused, injected or specialty products that retail pharmacies do not buy at NADAC "
              "rates. The erosion chart states how many molecules sit behind each line."))
    ratio = _one(con, """
        with t as (select u.spend / u.units / n.p as r from rx_units u join nadac_year n on n.ndc11 = u.ndc11 and n.y = u.year
                   join dim_ndc d on d.ndc11 = u.ndc11 where u.year = 2025 and d.segment = 'Generic' and u.units > 0 and u.spend > 0)
        select quantile_cont(r, 0.5) from t""")[0]
    add(Check("C19", "Consistency", "Medicaid spend per unit against NADAC price per unit (generics, 2025)",
              f"median ratio {ratio:.2f}", "between 0.8 and 3", "pass" if 0.8 <= ratio <= 3 else "warn",
              "If the two sources counted units differently the ratio would sit near 0.01 or 100. A ratio above 1 "
              "is expected: Medicaid reimburses ingredient cost plus a dispensing fee, and the fee weighs most on "
              "cheap generics. That fee is also why the Medicaid price effect is compared with NADAC's, not equated."))
    chg = _one(con, "select count(*) from fact_change")[0]
    chg_year = _one(con, "select sum(changes) from mart_events_year")[0]
    add(Check("C20", "Reconciliation", "Change counts by year add up to the change table",
              f"{chg_year:,} vs {chg:,}", "equal", "pass" if chg == chg_year else "fail", ""))
    fam = _one(con, "select count(*) filter (where in_nadac), count(*) from mart_merck")
    add(Check("C21", "Coverage", "Merck product families with a retail NADAC price",
              f"{fam[0]} of {fam[1]}", "report", "info",
              "Keytruda, Winrevair, Bridion, Zerbaxa, Prevymis and Welireg are not priced by NADAC; the page lists them as such."))
    return checks


def write(checks: list[Check]) -> None:
    MARTS.mkdir(parents=True, exist_ok=True)
    with open(MARTS / "dq_checks.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(asdict(checks[0])), lineterminator="\n")
        w.writeheader()
        for c in checks:
            w.writerow(asdict(c))
    counts = {s: sum(1 for c in checks if c.status == s) for s in ("pass", "warn", "fail", "info")}
    lines = [
        "# Data-quality scorecard",
        "",
        f"{len(checks)} checks run against the warehouse built from the NADAC files. "
        f"{counts['pass']} pass, {counts['warn']} warn, {counts['fail']} fail, {counts['info']} are measurements with no rule.",
        "",
        "Regenerate with `python -m pw.dq`. Failures and warnings come first.",
        "",
    ]
    order = {"fail": 0, "warn": 1, "pass": 2, "info": 3}
    for c in sorted(checks, key=lambda c: (order[c.status], c.id)):
        lines += [f"## {c.id} {c.name}", "", f"- **Status:** {c.status}", f"- **Result:** {c.result}",
                  f"- **Rule:** {c.rule}"]
        if c.note:
            lines.append(f"- **Note:** {c.note}")
        lines.append("")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "data-quality-scorecard.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    con = connect(read_only=True)
    checks = run(con)
    write(checks)
    for c in checks:
        print(f"{c.id} {c.status:<5} {c.name}: {c.result}")
    return 1 if any(c.status == "fail" for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
