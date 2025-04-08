"""Weekly watch: download this year's NADAC file, check it, and report the latest monthly update.

    python -m pw.refresh                  # download the current year, check, write data/marts/watch.json
    python -m pw.refresh --file x.csv --expected 12345 --year 2026     # use a local file (tests, offline)

This is the small job the weekly GitHub Action runs. It does not rebuild the 14-year warehouse (that takes about ten
minutes and 1.6 GB); it downloads only the current year (about 110 MB), and it
  * checks the file against the portal's own row count, 11-digit NDCs, positive prices, consecutive weeks, freshness;
  * summarises the most recent bulk update (how many packs moved, up and down, the biggest by annual value is left to
    the full build);
  * follows the packs named in data/ref/watch.csv (generic sitagliptin: how many packs are priced and whether its rate
    moves; Januvia's rate), and flags a change since the last run;
  * appends one line to data/marts/weekly_log.csv.
It exits non-zero when a check fails, so the Action goes red instead of publishing something wrong.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb
import requests

from .fetch import HEADERS
from .sources import MARTS, RAW, REF, all_sources

WATCH_JSON = MARTS / "watch.json"
LOG = MARTS / "weekly_log.csv"
SITE_COPY = MARTS.parent.parent / "dashboard" / "public" / "data" / "watch.json"
LOG_FIELDS = ["checked", "latest_week", "rows", "packs", "weeks_in_file", "latest_update", "changes", "ups", "downs",
              "material", "median_change", "watch_flags", "status"]


def load_watches(path: Path = REF / "watch.csv") -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def analyse(csv_path: Path, expected_rows: int | None, watches: list[dict], today: date | None = None,
            previous: dict | None = None) -> dict:
    """Read one NADAC year file and return the checks, the latest update and the watch results.

    `previous` is the last run's report; a presence watch flags when the number of matching packs differs from it."""
    today = today or date.today()
    con = duckdb.connect()
    con.execute(f"""
        create table raw as select * from read_csv('{csv_path.as_posix()}', all_varchar = true, normalize_names = true)""")
    con.execute("""
        create table t as
        select ndc, ndc_description as description, try_cast(nadac_per_unit as double) as price,
               try_strptime(as_of_date, '%m/%d/%Y')::date as as_of, classification_for_rate_setting as cls
        from raw""")
    rows = con.execute("select count(*) from raw").fetchone()[0]
    bad_ndc = con.execute("select count(*) from t where not regexp_matches(ndc, '^[0-9]{11}$')").fetchone()[0]
    bad_price = con.execute("select count(*) from t where price is null or price <= 0").fetchone()[0]
    bad_date = con.execute("select count(*) from t where as_of is null").fetchone()[0]
    dup = con.execute("select count(*) from (select ndc, as_of from t group by 1, 2 having count(*) > 1)").fetchone()[0]
    packs, weeks, first, latest = con.execute("select count(distinct ndc), count(distinct as_of), min(as_of), max(as_of) from t").fetchone()
    gaps = con.execute("""select count(*) from (select date_diff('day', lag(d) over (order by d), d) g
                          from (select distinct as_of d from t)) where g not in (6, 7, 8)""").fetchone()[0]
    age = (today - latest).days
    checks = [
        {"name": "Rows equal the portal's row count", "ok": expected_rows is None or rows == expected_rows,
         "value": f"{rows:,} vs {expected_rows:,}" if expected_rows is not None else f"{rows:,} (no count given)"},
        {"name": "Every NDC has 11 digits", "ok": bad_ndc == 0, "value": f"{bad_ndc} bad"},
        {"name": "Every price is a positive number", "ok": bad_price == 0, "value": f"{bad_price} bad"},
        {"name": "Every date can be read", "ok": bad_date == 0, "value": f"{bad_date} bad"},
        {"name": "One price per pack per week", "ok": dup == 0, "value": f"{dup} duplicated"},
        {"name": "Weekly snapshots are consecutive", "ok": gaps == 0, "value": f"{gaps} gaps"},
        {"name": "Newest snapshot is under 14 days old", "ok": age <= 14, "value": f"{age} days ({latest.isoformat()})"},
    ]
    # week-on-week changes, then the most recent bulk update (a week with more than 1,000 changes)
    con.execute("""
        create table chg as
        select ndc, description, as_of, price, lag(price) over (partition by ndc order by as_of) as prev,
               date_diff('day', lag(as_of) over (partition by ndc order by as_of), as_of) as gap
        from t""")
    con.execute("""create table moved as
        select ndc, description, as_of, price, prev, price / prev - 1 as pct from chg
        where prev is not null and gap <= 10 and abs(price - prev) > 1e-9 and price / prev between 0.1 and 10""")
    bulk = con.execute("select max(as_of) from (select as_of from moved group by as_of having count(*) > 1000)").fetchone()[0]
    update = None
    if bulk:
        n, up, down, med, mat = con.execute("""
            select count(*), count(*) filter (where pct > 0), count(*) filter (where pct < 0),
                   quantile_cont(pct, 0.5), count(*) filter (where abs(pct) >= 0.01)
            from moved where as_of = ?""", [bulk]).fetchone()
        update = {"date": bulk.isoformat(), "changes": n, "ups": up, "downs": down, "material": mat,
                  "medianChange": round(med, 5)}
    # watches
    results = []
    for w in watches:
        pat = re.compile(w["pattern"], re.I)
        # one hit per pack (NDC), not per description: 28 generic sitagliptin packs share five descriptions
        hits = [(n, d, c) for n, d, c in con.execute(
            "select distinct ndc, description, cls from t where as_of = ?", [latest]).fetchall()
            if pat.search(d) and (not w["class"] or c == w["class"])]
        names = sorted({d for _, d, _ in hits})
        res = {"name": w["name"], "kind": w["kind"], "pattern": w["pattern"], "class": w["class"], "why": w["why"],
               "found": len(hits), "packs": names[:8], "moves": []}
        if w["kind"] == "rate":
            # a rate watch: flag a move of 5% or more in the latest bulk update
            if bulk:
                res["moves"] = [{"pack": d, "from": round(p0, 4), "to": round(p1, 4), "pct": round(pc, 4)}
                                for d, p0, p1, pc in con.execute(
                                    """select description, prev, price, pct from moved
                                       where as_of = ? and regexp_matches(description, ?, 'i') and abs(pct) >= 0.05
                                       order by abs(pct) desc limit 8""", [bulk, w["pattern"]]).fetchall()]
            res["flag"] = bool(res["moves"])
        else:
            # a presence watch: flag when the number of matching packs differs from the last run
            before = next((p["found"] for p in (previous or {}).get("watches", []) if p["name"] == w["name"]), None)
            res["previous"] = before
            res["flag"] = before is not None and before != len(hits)
        results.append(res)
    flags = [r["name"] for r in results if r["flag"]]
    ok = all(c["ok"] for c in checks)
    return {"checked": today.isoformat(), "latestWeek": latest.isoformat(), "firstWeek": first.isoformat(), "rows": rows,
            "packs": packs, "weeksInFile": weeks, "checks": checks, "latestUpdate": update, "watches": results,
            "flags": flags, "status": "ok" if ok else "FAILED"}


def write(report: dict) -> None:
    MARTS.mkdir(parents=True, exist_ok=True)
    WATCH_JSON.write_text(json.dumps(report, indent=1), encoding="utf-8")
    if SITE_COPY.parent.exists():
        SITE_COPY.write_text(json.dumps(report, separators=(",", ":")), encoding="utf-8")
    new = not LOG.exists()
    u = report["latestUpdate"] or {}
    with LOG.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=LOG_FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow({"checked": report["checked"], "latest_week": report["latestWeek"], "rows": report["rows"],
                    "packs": report["packs"], "weeks_in_file": report["weeksInFile"], "latest_update": u.get("date", ""),
                    "changes": u.get("changes", ""), "ups": u.get("ups", ""), "downs": u.get("downs", ""),
                    "material": u.get("material", ""), "median_change": u.get("medianChange", ""),
                    "watch_flags": "; ".join(report["flags"]), "status": report["status"]})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", help="analyse this local NADAC CSV instead of downloading")
    ap.add_argument("--expected", type=int, help="expected row count when --file is given")
    ap.add_argument("--year", type=int, default=date.today().year)
    args = ap.parse_args(argv)
    if args.file:
        path, expected = Path(args.file), args.expected
    else:
        src = next(s for s in all_sources() if s.key == f"nadac_{args.year}")
        r = requests.get(src.count_url, headers=HEADERS, timeout=60)
        r.raise_for_status()
        expected = int(r.json()["count"])
        path = RAW / src.filename
        RAW.mkdir(parents=True, exist_ok=True)
        with requests.get(src.url, headers=HEADERS, stream=True, timeout=(30, 300)) as resp:
            resp.raise_for_status()
            with open(path, "wb") as fh:
                for block in resp.iter_content(1 << 20):
                    fh.write(block)
    previous = json.loads(WATCH_JSON.read_text(encoding="utf-8")) if WATCH_JSON.exists() else None
    report = analyse(path, expected, load_watches(), previous=previous)
    write(report)
    for c in report["checks"]:
        print(f"{'ok  ' if c['ok'] else 'FAIL'} {c['name']}: {c['value']}")
    print(f"latest week {report['latestWeek']}; latest bulk update {report['latestUpdate']}")
    for w in report["watches"]:
        print(f"watch: {w['name']}: {w['found']} pack(s){' <- FLAG' if w['flag'] else ''}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
