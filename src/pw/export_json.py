"""Write the small JSON files the dashboard reads (dashboard/public/data/*.json).

    python -m pw.export_json

Every number the page, the README and the CV quote comes from headline.json, which is computed here from the
warehouse; nothing is typed in by hand.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import duckdb

from .build import connect
from .sources import MARTS, RAW, ROOT

OUT = ROOT / "dashboard" / "public" / "data"
SEGMENTS = ["All", "Brand", "Generic", "Branded generic", "Biologic"]


def _write(name: str, payload: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def _r(x: float | None, d: int = 2) -> float | None:
    return None if x is None else round(float(x), d)


def _iso(x) -> str | None:
    return None if x is None else x.isoformat()


def export_index(con) -> dict:
    rows = con.execute("""select kind, grp, strftime(month, '%Y-%m') as m, equal_weight, weighted, ndcs
                          from mart_index_month order by kind, grp, month""").fetchall()
    months = sorted({r[2] for r in rows if r[0] == "segment" and r[1] == "All"})
    pos = {m: i for i, m in enumerate(months)}
    series: dict[str, dict] = {}
    ndcs: list[int | None] = [None] * len(months)
    for kind, grp, m, eq, w, n in rows:
        key = f"{kind}:{grp}"
        s = series.setdefault(key, {"equal": [None] * len(months), "weighted": [None] * len(months)})
        if m in pos:
            s["equal"][pos[m]] = _r(eq)
            s["weighted"][pos[m]] = _r(w)
            if key == "segment:All":
                ndcs[pos[m]] = int(n)
    # drop the incomplete last month from line charts? keep it, but say how many weeks it holds
    weeks = dict(con.execute("select strftime(month, '%Y-%m'), weeks from mart_index_month where kind='segment' and grp='All'").fetchall())
    payload = {"months": months, "weeksInMonth": [int(weeks.get(m, 0)) for m in months], "packsMatched": ndcs,
               "series": series, "weightedFrom": "2019-01", "base": {"weighted": "2019-01-02", "equal": "2013-12-05"}}
    _write("index.json", payload)
    return payload


def export_events(con) -> dict:
    years = {}
    for y, seg, priced, changes, mat, ups, downs, mups, mdowns, steps, med_up, med_dn, imp_up, imp_dn, share in con.execute(
        """select y, segment, ndcs_priced, changes, material_changes, ups, downs, material_ups, material_downs,
                  steps_up_2pct, median_up, median_down, impact_up, impact_down, share_of_ndc_weeks_changed
           from mart_events_year where segment in ('Brand', 'Generic') order by y, segment""").fetchall():
        years.setdefault(int(y), {})[seg.lower()] = {
            "priced": int(priced), "changes": int(changes), "material": int(mat), "ups": int(ups), "downs": int(downs),
            "materialUps": int(mups), "materialDowns": int(mdowns), "steps2": int(steps), "medianUp": _r(med_up, 4),
            "medianDown": _r(med_dn, 4), "shareOfWeeksChanged": _r(share, 4)}
    season = [{"m": int(m), "brandUp2": int(a), "brandDown2": int(b), "brandChanges": int(c)}
              for m, a, b, c in con.execute("""select m, steps_up_2pct, steps_down_2pct, changes from mart_events_season
                                                where segment = 'Brand' order by m""").fetchall()]
    sh = con.execute("""select y, count(*) filter (where abs(pct) < 0.005) * 1.0 / count(*)
                        from fact_change where segment = 'Brand' group by y order by y""").fetchall()
    drift = [{"y": int(y), "shareUnderHalfPercent": _r(v, 4)} for y, v in sh]
    bulk = [{"date": _iso(d), "changes": int(n)} for d, n in con.execute(
        """select as_of, count(*) from fact_change where y >= 2025 group by as_of having count(*) > 1000
           order by as_of""").fetchall()]
    payload = {"years": [{"y": y, **v} for y, v in sorted(years.items())], "season": season, "drift": drift,
               "bulkUpdates": bulk}
    _write("events.json", payload)
    return payload


def export_movers(con) -> dict:
    cols = ["scope", "label", "ndc11", "description", "segment", "owner", "family", "as_of", "prev_price", "price", "pct",
            "units", "annual_impact"]
    rows = con.execute("select " + ", ".join(cols) + " from mart_movers order by scope, label, abs(annual_impact) desc").fetchall()
    out: dict[str, list] = {}
    for r in rows:
        d = dict(zip(cols, r))
        key = "latest" if d["scope"] == "latest" else d["label"]
        out.setdefault(key, []).append({
            "ndc": d["ndc11"], "name": d["description"], "segment": d["segment"], "owner": d["owner"],
            "family": d["family"], "date": _iso(d["as_of"]), "from": _r(d["prev_price"], 4), "to": _r(d["price"], 4),
            "pct": _r(d["pct"], 4), "units": _r(d["units"], 0), "annualValue": _r(d["annual_impact"], 0)})
    latest = con.execute("select as_of from latest_update").fetchone()[0]
    stats = con.execute("""select count(*), count(*) filter (where pct > 0), count(*) filter (where pct < 0),
                                  quantile_cont(pct, 0.5), count(*) filter (where abs(pct) >= 0.01)
                           from fact_change where as_of = (select as_of from latest_update)""").fetchone()
    payload = {"latestUpdate": _iso(latest), "changes": int(stats[0]), "ups": int(stats[1]), "downs": int(stats[2]),
               "medianChange": _r(stats[3], 4), "material": int(stats[4]), "lists": out}
    _write("movers.json", payload)
    return payload


def export_erosion(con) -> dict:
    cohort = {}
    for side, k, med, p25, p75, n in con.execute(
            "select side, k, median_index, p25, p75, events from mart_erosion_cohort order by side, k").fetchall():
        cohort.setdefault(side, []).append({"k": int(k), "median": _r(med, 1), "p25": _r(p25, 1), "p75": _r(p75, 1),
                                            "events": int(n)})
    events = []
    for r in con.execute("""select ingredient, brand_family, entry_quarter, brand_run_rate_before_musd, brand_price_q4,
                                   brand_price_q8, generic_price_q4, generic_price_q8, brand_spend_q4, brand_spend_q8
                            from mart_erosion_events_price order by brand_run_rate_before_musd desc nulls last""").fetchall():
        events.append({"ingredient": r[0], "brand": r[1], "entry": _iso(r[2]), "runRateMusd": _r(r[3], 0),
                       "brandPriceQ4": _r(r[4], 1), "brandPriceQ8": _r(r[5], 1), "genericPriceQ4": _r(r[6], 1),
                       "genericPriceQ8": _r(r[7], 1), "brandSpendQ4": _r(r[8], 1), "brandSpendQ8": _r(r[9], 1)})
    sp = con.execute("select brand_spend_q4_median, brand_spend_q8_median, events_q4, events_q8 from mart_scenario_spend").fetchone()
    payload = {"cohort": cohort, "events": events,
               "spendMedian": {"q4": _r(sp[0], 1), "q8": _r(sp[1], 1), "eventsQ4": int(sp[2]), "eventsQ8": int(sp[3])}}
    _write("erosion.json", payload)
    return payload


def export_merck(con) -> dict:
    rows = []
    for r in con.execute("""select family, franchise, area, spend_2025, status, core_end, pack, price_2019, price_2022,
                                   price_2025, price_latest, change_since_2019, family_index_now, in_nadac
                            from mart_merck order by spend_2025 desc""").fetchall():
        rows.append({"family": r[0], "franchise": r[1], "area": r[2], "spend2025": _r(r[3], 0), "status": r[4],
                     "coreEnd": _iso(r[5]), "pack": r[6], "price2019": _r(r[7], 3), "price2022": _r(r[8], 3),
                     "price2025": _r(r[9], 3), "priceLatest": _r(r[10], 3), "changeSince2019": _r(r[11], 4),
                     "familyIndex": _r(r[12], 1), "inNadac": bool(r[13])})
    brand_now = con.execute("select max(brand_index_now) from mart_merck").fetchone()[0]
    n_gen, n_lab, first_gen, n_brand = con.execute(
        "select generic_packs, generic_labelers, generic_first_week, brand_packs from mart_sitagliptin_summary").fetchone()
    rates = [{"strength": r[0], "genericPacks": int(r[1]), "genericRate": _r(r[2], 4), "januviaRate": _r(r[3], 4),
              "ratio": _r(r[4], 4)} for r in con.execute("select * from mart_sitagliptin_rates").fetchall()]
    payload = {"families": rows, "brandIndexNow": _r(brand_now, 1),
               "sitagliptin": {"genericPacks": int(n_gen), "genericLabelers": int(n_lab), "genericFirstWeek": _iso(first_gen),
                               "brandPacks": int(n_brand), "rates": rates}}
    _write("merck.json", payload)
    return payload


def export_triangulation(con) -> dict:
    out = []
    for r in con.execute("""select y0, y1, segment, ndcs, coverage_of_spend, coverage_of_units, nadac_effect, medicaid_effect,
                                   nadac_change, medicaid_change, rank_corr from mart_triangulation order by y0, y1, segment""").fetchall():
        out.append({"y0": int(r[0]), "y1": int(r[1]), "segment": r[2], "packs": int(r[3]), "coverageSpend": _r(r[4], 4),
                    "coverageUnits": _r(r[5], 4), "nadacEffect": _r(r[6], 0), "medicaidEffect": _r(r[7], 0),
                    "nadacChange": _r(r[8], 4), "medicaidChange": _r(r[9], 4), "rankCorr": _r(r[10], 3)})
    rx = [{"y0": int(a), "y1": int(b), "rxPriceEffect": _r(c, 0), "rxSpendChange": _r(d, 0)}
          for a, b, c, d in con.execute("select y0, y1, rx_price_effect, rx_spend_change from mart_triangulation_rx").fetchall()]
    payload = {"pairs": out, "rx": rx}
    _write("triangulation.json", payload)
    return payload


def export_quality() -> list[dict]:
    with (MARTS / "dq_checks.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    _write("quality.json", rows)
    return rows


def headline(con, idx: dict, ev: dict, mv: dict, ero: dict, mer: dict, tri: dict, quality: list[dict]) -> dict:
    s = idx["series"]
    last = len(idx["months"]) - 1
    def w(key): return s[key]["weighted"][last]
    def e(key): return s[key]["equal"][last]
    # seasonality: how concentrated are brand steps of 2% or more?
    tot = sum(x["brandUp2"] for x in ev["season"])
    by_m = {x["m"]: x["brandUp2"] for x in ev["season"]}
    jan, jul = by_m[1] / tot, by_m[7] / tot
    # the biggest single step of the Januvia headline pack
    jan_pack = con.execute("select ndc11, description from merck_pack where family = 'JANUVIA'").fetchone()
    step = con.execute("select as_of, prev_price, price, pct from fact_change where ndc11 = ? order by pct limit 1",
                       [jan_pack[0]]).fetchone()
    sita = mer["sitagliptin"]
    r100 = next(r for r in sita["rates"] if r["strength"] == "100 MG")
    core = con.execute("select core_end from rx_merck where family = 'JANUVIA'").fetchone()[0]
    t = {(p["y0"], p["y1"], p["segment"]): p for p in tri["pairs"]}
    rxp = {(p["y0"], p["y1"]): p for p in tri["rx"]}
    t_all, t_brand = t[(2022, 2025, "All")], t[(2022, 2025, "Brand")]
    coh_b = {c["k"]: c for c in ero["cohort"]["brand"]}
    coh_g = {c["k"]: c for c in ero["cohort"]["generic"]}
    n_rows, n_ndc, n_wk, first, lastw = con.execute(
        "select count(*), count(distinct ndc11), count(distinct as_of), min(as_of), max(as_of) from fact_nadac").fetchone()
    sources = {"stagedRows": con.execute("select count(*) from stg_nadac").fetchone()[0]}
    checks = {st: sum(1 for c in quality if c["status"] == st) for st in ("pass", "warn", "fail", "info")}
    head = {
        "asOf": _iso(lastw), "firstWeek": _iso(first), "weeks": int(n_wk), "factRows": int(n_rows), "packs": int(n_ndc),
        "stagedRows": int(sources["stagedRows"]), "latestUpdate": mv["latestUpdate"],
        "index": {"month": idx["months"][last], "base": "2019-01",
                  "weighted": {"all": w("segment:All"), "brand": w("segment:Brand"), "generic": w("segment:Generic")},
                  "equalWeight": {"all": e("segment:All"), "brand": e("segment:Brand"), "generic": e("segment:Generic")}},
        "seasonality": {"brandSteps": tot, "january": _r(jan, 4), "july": _r(jul, 4), "janJul": _r(jan + jul, 4)},
        "erosion": {"molecules": len(ero["events"]), "brandPriced": coh_b[-1]["events"],
                    "genericPriced": max(c["events"] for c in ero["cohort"]["generic"]),
                    "brandPriceQ8": coh_b[8]["median"], "genericPriceQ8": coh_g[8]["median"],
                    "genericPriceQ12": coh_g[12]["median"], "brandSpendQ8": ero["spendMedian"]["q8"],
                    "brandSpendQ4": ero["spendMedian"]["q4"], "brandPriceQ4": coh_b[4]["median"]},
        "triangulation": {"y0": 2022, "y1": 2025, "coverageSpend": t_all["coverageSpend"],
                          "coverageUnits": t_all["coverageUnits"], "rxPriceEffect": rxp[(2022, 2025)]["rxPriceEffect"],
                          "all": {"nadac": t_all["nadacEffect"], "medicaid": t_all["medicaidEffect"], "corr": t_all["rankCorr"]},
                          "brand": {"nadac": t_brand["nadacEffect"], "medicaid": t_brand["medicaidEffect"],
                                    "corr": t_brand["rankCorr"], "coverageSpend": t_brand["coverageSpend"]}},
        "merck": {"januvia": {"pack": jan_pack[1], "stepDate": _iso(step[0]), "from": _r(step[1], 3), "to": _r(step[2], 3),
                              "stepPct": _r(step[3], 4)},
                  "sitagliptin": {"genericPacks": sita["genericPacks"], "genericLabelers": sita["genericLabelers"],
                                  "genericFirstWeek": sita["genericFirstWeek"], "genericRate100": r100["genericRate"],
                                  "januviaRate100": r100["januviaRate"], "ratio100": r100["ratio"]},
                  "coreEnd": _iso(core),
                  "brandIndexNow": mer["brandIndexNow"], "priced": sum(1 for f in mer["families"] if f["inNadac"]),
                  "families": len(mer["families"])},
        "latest": {"date": mv["latestUpdate"], "changes": mv["changes"], "ups": mv["ups"], "downs": mv["downs"],
                   "material": mv["material"], "medianChange": mv["medianChange"]},
        "checks": {**checks, "total": len(quality)},
    }
    _write("headline.json", head)
    return head


def export_meta(con) -> None:
    exp = json.loads((RAW / "expected_rows.json").read_text()) if (RAW / "expected_rows.json").exists() else {}
    meta = {
        "built": date.today().isoformat(),
        "sources": [
            {"name": "NADAC (National Average Drug Acquisition Cost), weekly rates 2013-2026",
             "publisher": "CMS, via data.medicaid.gov", "url": "https://data.medicaid.gov/dataset/dfa2ab14-06c2-457a-9e36-5cb6d80f8d93"},
            {"name": "State Drug Utilization Data 2019-2025 (units and spend by product)",
             "publisher": "CMS, via Rx Market Pulse", "url": "https://github.com/f20230125-sudo/rx-market-pulse"},
        ],
        "expectedRows": exp,
    }
    _write("meta.json", meta)


def main() -> int:
    con = connect(read_only=True)
    idx = export_index(con)
    ev = export_events(con)
    mv = export_movers(con)
    ero = export_erosion(con)
    mer = export_merck(con)
    tri = export_triangulation(con)
    quality = export_quality()
    head = headline(con, idx, ev, mv, ero, mer, tri, quality)
    export_meta(con)
    print(json.dumps(head, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
