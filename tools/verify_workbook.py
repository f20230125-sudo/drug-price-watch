"""Compare Excel's own results with an independent calculation.

    python tools/verify_workbook.py <probe.json>

tools/excel_probe.ps1 drives Excel through the scenarios in excel/probe_scenarios.json and writes what Excel's formulas
returned. This script recomputes every Tracker, Entry scenario and Checks cell from data/marts/xl_products.csv and
data/marts/xl_class_index.csv with plain Python (no shared code with src/pw/workbook.py, no spreadsheet engine) and
compares them: text exactly, numbers to 1e-9 relative.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YEARS = list(range(2013, 2027))
TOL = 1e-9
NA = "n/a"


def load():
    with (ROOT / "data" / "marts" / "xl_products.csv").open(encoding="utf-8", newline="") as fh:
        products = list(csv.DictReader(fh))
    with (ROOT / "data" / "marts" / "xl_class_index.csv").open(encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        index = {int(r["year"]): {k: (float(v) if v != "" else None) for k, v in r.items() if k != "year"} for r in rd}
    return products, index


def price(p: dict, y: int):
    v = p[f"p{y}"]
    return float(v) if v != "" else None


def round8(x: float) -> float:
    return float(Decimal(repr(x)).quantize(Decimal("1e-8"), rounding=ROUND_HALF_UP))


def expected(sc: dict, products: list[dict], index: dict) -> dict:
    p = next(x for x in products if x["label"] == sc["product"])
    base, end, comp = sc["base"], sc["end"], sc["compare"]
    pb, pe = price(p, base), price(p, end)
    both = pb is not None and pe is not None
    change = pe / pb - 1 if both else NA
    cagr = (pe / pb) ** (1 / (end - base)) - 1 if both and end > base else NA
    ib, ie = index[base][comp], index[end][comp]
    gchange = ie / ib - 1 if ib is not None and ie is not None else NA
    rel = (change - gchange) * 100 if change != NA and gchange != NA else NA
    units = float(p["units_2025"])
    value = (pe - pb) * units if both else NA
    changes = []
    for q in products:
        a, b = price(q, base), price(q, end)
        if a is not None and b is not None:
            changes.append(round8(b / a - 1))
    share = (sum(1 for c in changes if c < round8(change)) / len(changes)) if change != NA and changes else NA
    single = {"B4": p["description"], "B5": p["ndc"], "B6": p["segment"], "B7": p["area"], "B8": p["owner"],
              "B9": p["unit"], "B11": pb if pb is not None else NA, "B12": pe if pe is not None else NA, "B13": change,
              "B14": cagr, "B16": gchange, "B17": rel, "B19": units, "B20": value, "B21": float(p["latest_price"]),
              "B22": float(len(changes)), "B23": share}
    years = []
    for i, y in enumerate(YEARS):
        py = price(p, y)
        ix = index[y][comp]
        prev_p = price(p, y - 1) if i else None
        prev_i = index[y - 1][comp] if i else None
        years.append([float(y), py if py is not None else None,
                      (py / prev_p - 1) if i and py is not None and prev_p is not None else None,
                      ix if ix is not None else None,
                      (ix / prev_i - 1) if i and ix is not None and prev_i is not None else None])
    latest = float(p["latest_price"])
    t = [[latest, units, latest * units, 1.0],
         [latest * (1 + sc["move4"] / 100), units * sc["keep4"] / 100, 0.0, 0.0],
         [latest * (1 + sc["move8"] / 100), units * sc["keep8"] / 100, 0.0, 0.0]]
    for r in t[1:]:
        r[2] = r[0] * r[1]
    t[1][3] = t[1][2] / t[0][2]
    t[2][3] = t[2][2] / t[0][2]
    spend_total = sum(float(x["spend_2025"]) for x in products)
    checks = ["OK",
              "OK" if base < end else "CHECK",
              "OK" if both else "CHECK",
              "OK" if gchange != NA else "CHECK",
              "OK" if all(0 <= sc[k] <= 100 for k in ("keep4", "keep8")) else "CHECK",
              "OK"]
    overall = "ALL OK" if all(c == "OK" for c in checks) else "CHECK"
    return {"single": single, "years": years, "scen": {"B4": p["description"], "B5": latest, "B6": units}, "table": t,
            "checks": checks, "overall": overall, "row": float(next(i for i, x in enumerate(products) if x["label"] == sc["product"]) + 1),
            "spend_total": spend_total}


def same(a, b) -> bool:
    if a is None and b is None:
        return True
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    if a is None or b is None:
        # Excel returns "" (read as None) for a blank formula result
        return False
    return math.isclose(float(a), float(b), rel_tol=TOL, abs_tol=1e-12)


def main(argv: list[str]) -> int:
    probe = json.loads(Path(argv[1]).read_text(encoding="utf-8-sig"))
    products, index = load()
    bad, n = [], 0
    for res in probe:
        sc = res["inputs"]
        exp = expected(sc, products, index)

        def cmp(name, got, want):
            nonlocal n
            n += 1
            if not same(got, want):
                bad.append(f"{res['id']} {name}: Excel {got!r} vs Python {want!r}")
        for cell, want in exp["single"].items():
            cmp(f"Tracker!{cell}", res["tracker"].get(cell), want)
        for i, (g, w) in enumerate(zip(res["years"], exp["years"])):
            for j in range(5):
                cmp(f"Tracker!year{i}.{j}", None if g[j] in ("", None) else g[j], w[j])
        for cell, want in exp["scen"].items():
            cmp(f"Scenario!{cell}", res["scenario"].get(cell), want)
        for i in range(3):
            for j in range(4):
                cmp(f"Scenario!table{i}.{j}", res["table"][i][j], exp["table"][i][j])
        for i, (g, w) in enumerate(zip(res["checks"], exp["checks"])):
            cmp(f"Checks!{i}", g, w)
        cmp("Checks!overall", res["overall"], exp["overall"])
        cmp("Inputs!row", res["row"], exp["row"])
    if bad:
        print(f"{len(bad)} of {n} cells differ:")
        for b in bad[:25]:
            print("  ", b)
        return 1
    print(f"{len(probe)} scenarios OK: {n} cells match the independent calculation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
