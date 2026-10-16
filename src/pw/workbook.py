"""Price Tracker: an Excel workbook for following one drug's NADAC price against its class and asking "what if generics arrive".

    python -m pw.workbook            # writes excel/Price-Tracker.xlsx

Pick a pack (a drug, strength and package) and two years on the Inputs sheet. The Tracker sheet is made of live
formulas (INDEX/MATCH into the Products and Class index sheets, COUNTIF for rank): the pack's price in each year, how
far it moved, how the class moved, the gap between the two, what the move is worth at 2025 Medicaid volume, and where the
pack sits among the 1,000 packs with the most Medicaid spend. The Entry scenario sheet turns a price move and a volume
loss after generic entry into an annual value, starting from the cohort medians found in this project.

No result is pasted in. The Products sheet holds one row per pack, the Class index sheet one row per year, and
data/marts/xl_*.csv holds the same numbers so tools/verify_workbook.py can recompute everything without this module.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import xlsxwriter

from .build import connect
from .sources import MARTS, ROOT

OUT = ROOT / "excel" / "Price-Tracker.xlsx"
PROBE = ROOT / "excel" / "probe_scenarios.json"

INK = "#1B2A3A"
ACCENT = "#B4531E"  # the accent of this project's site
ACCENT_LIGHT = "#F6E3D7"
SLATE = "#5B6672"
RULE = "#D9DEE3"
INPUT_FILL = "#FFF6D6"
INPUT_FONT = "#1D4ED8"

YEARS = list(range(2013, 2027))
N_PACKS = 1000


def collect(con) -> tuple[list[dict], dict, list[str], dict]:
    """Products (top packs by 2025 Medicaid spend, plus the Merck headline packs), annual class index, groups, cohort."""
    rows = con.execute(f"""
        with yr as (select ndc11, year(as_of)::integer as y, avg(price) as p from fact_nadac
                    group by 1, 2 having count(*) >= 20),
        latest as (select ndc11, arg_max(price, as_of) as p from fact_nadac group by 1),
        spend as (select ndc11, units, spend from rx_units where year = 2025 and units > 0 and spend > 0),
        pick as (
            select d.ndc11 from dim_ndc d join spend s using (ndc11)
            where d.last_week = (select max(as_of) from fact_nadac)
            order by s.spend desc limit {N_PACKS}
        ),
        keep as (select ndc11 from pick union select ndc11 from merck_pack)
        select d.ndc11, d.description, d.segment, coalesce(d.area, ''), coalesce(d.owner, ''), coalesce(d.family, ''),
               d.pricing_unit, coalesce(s.units, 0), coalesce(s.spend, 0), l.p
        from keep k join dim_ndc d using (ndc11) join latest l using (ndc11) left join spend s using (ndc11)
        order by coalesce(s.spend, 0) desc, d.ndc11""").fetchall()
    prices: dict[str, dict[int, float]] = {}
    for ndc, y, p in con.execute("""select ndc11, year(as_of)::integer, avg(price) from fact_nadac
                                    group by 1, 2 having count(*) >= 20""").fetchall():
        prices.setdefault(ndc, {})[y] = p
    products = []
    seen = set()
    for ndc, desc, seg, area, owner, fam, unit, units, spend, latest in rows:
        label = f"{desc} [{ndc}]"
        if label in seen:
            continue
        seen.add(label)
        products.append({"label": label, "ndc": ndc, "description": desc, "segment": seg, "area": area, "owner": owner,
                         "family": fam, "unit": unit, "units": float(units), "spend": float(spend),
                         "latest": float(latest), "prices": {y: prices.get(ndc, {}).get(y) for y in YEARS}})
    # annual average of the monthly equal-weight index, per class
    groups = ["All packs", "Brand", "Generic", "Branded generic", "Biologic"]
    seg_name = {"All packs": "All", "Brand": "Brand", "Generic": "Generic", "Branded generic": "Branded generic",
                "Biologic": "Biologic"}
    areas = [a for (a,) in con.execute("select distinct grp from mart_index_month where kind = 'area' order by grp").fetchall()]
    index: dict[str, dict[int, float | None]] = {}
    for g in groups:
        index[g] = {y: None for y in YEARS}
        for y, v in con.execute("""select year(month)::integer, avg(equal_weight) from mart_index_month
                                   where kind = 'segment' and grp = ? group by 1""", [seg_name[g]]).fetchall():
            index[g][y] = v
    for a in areas:
        index[a] = {y: None for y in YEARS}
        for y, v in con.execute("""select year(month)::integer, avg(equal_weight) from mart_index_month
                                   where kind = 'area' and grp = ? group by 1""", [a]).fetchall():
            index[a][y] = v
    cohort = {}
    for side, k, med in con.execute("select side, k, median_index from mart_erosion_cohort order by side, k").fetchall():
        cohort[(side, int(k))] = med
    sp = con.execute("select brand_spend_q4_median, brand_spend_q8_median from mart_scenario_spend").fetchone()
    cohort["spend_q4"], cohort["spend_q8"] = sp
    return products, index, groups + areas, cohort


def write_csvs(products: list[dict], index: dict, group_names: list[str]) -> None:
    with (MARTS / "xl_products.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["label", "ndc", "description", "segment", "area", "owner", "family", "unit", "units_2025",
                    "spend_2025", "latest_price"] + [f"p{y}" for y in YEARS])
        for p in products:
            w.writerow([p["label"], p["ndc"], p["description"], p["segment"], p["area"], p["owner"], p["family"],
                        p["unit"], p["units"], p["spend"], p["latest"]] +
                       ["" if p["prices"][y] is None else repr(p["prices"][y]) for y in YEARS])
    with (MARTS / "xl_class_index.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["year"] + group_names)
        for y in YEARS:
            w.writerow([y] + ["" if index[g][y] is None else repr(index[g][y]) for g in group_names])


def probe_scenarios(products: list[dict], cohort: dict) -> list[dict]:
    """Six sets of inputs the probe tool feeds Excel; chosen to cover brand, generic, partial history and edge cases."""
    def find(sub: str, seg: str | None = None):
        for p in products:
            if sub in p["description"] and (seg is None or p["segment"] == seg):
                return p["label"]
        return products[0]["label"]
    k4 = cohort["spend_q4"] / cohort[("brand", 4)] * 100
    k8 = cohort["spend_q8"] / cohort[("brand", 8)] * 100
    d4, d8 = round(cohort[("brand", 4)] - 100, 1), round(cohort[("brand", 8)] - 100, 1)
    top = products[0]["label"]
    return [
        {"id": "S1", "product": find("JANUVIA 100 MG"), "compare": "Brand", "base": 2019, "end": 2025,
         "keep4": round(k4, 1), "keep8": round(k8, 1), "move4": d4, "move8": d8},
        {"id": "S2", "product": find("JANUMET 50-1,000"), "compare": "Diabetes & obesity", "base": 2022, "end": 2026,
         "keep4": 40, "keep8": 20, "move4": 0, "move8": -10},
        {"id": "S3", "product": top, "compare": "All packs", "base": 2016, "end": 2024,
         "keep4": 100, "keep8": 100, "move4": 0, "move8": 0},
        {"id": "S4", "product": find("ISENTRESS 400"), "compare": "Infectious disease (non-HIV)", "base": 2014, "end": 2020,
         "keep4": 25, "keep8": 10, "move4": 5, "move8": 8},
        {"id": "S5", "product": find("METFORMIN", "Generic"), "compare": "Generic", "base": 2018, "end": 2023,
         "keep4": 90, "keep8": 80, "move4": -20, "move8": -35},
        {"id": "S6", "product": find("BELSOMRA 20"), "compare": "Brand", "base": 2025, "end": 2026,
         "keep4": 0, "keep8": 0, "move4": 100, "move8": 0},
    ]


def build(path: Path = OUT) -> Path:
    con = connect(read_only=True)
    products, index, group_names, cohort = collect(con)
    asof = con.execute("select max(as_of) from fact_nadac").fetchone()[0]
    con.close()
    write_csvs(products, index, group_names)
    scenarios = probe_scenarios(products, cohort)
    PROBE.write_text(json.dumps(scenarios, indent=1), encoding="utf-8")
    n = len(products)
    last = n + 1

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(path))
    wb.set_calc_mode("auto")
    wb.set_properties({"title": "Price Tracker", "author": "Mohammad Uzair Khan",
                       "comments": f"Built from public CMS NADAC rates, data to {asof}."})
    base = {"font_name": "Calibri", "font_size": 10, "font_color": INK}
    f = lambda **kw: wb.add_format({**base, **kw})
    title = f(font_size=18, bold=True)
    sub = f(font_color=SLATE, italic=True)
    h = f(bold=True, font_color="white", bg_color=INK, valign="vcenter", text_wrap=True, align="center")
    h_left = f(bold=True, font_color="white", bg_color=INK, valign="vcenter", text_wrap=True)
    cell = f(bottom=1, bottom_color=RULE)
    cell_c = f(bottom=1, bottom_color=RULE, align="center")
    int0 = f(num_format="#,##0", bottom=1, bottom_color=RULE)
    price = f(num_format="$#,##0.00##", bottom=1, bottom_color=RULE)
    pct1 = f(num_format="0.0%", bottom=1, bottom_color=RULE)
    pp = f(num_format='+0.0" pp";-0.0" pp"', bottom=1, bottom_color=RULE)
    money = f(num_format='$#,##0;-$#,##0', bottom=1, bottom_color=RULE)
    idx = f(num_format="0.0", bottom=1, bottom_color=RULE)
    label = f(bold=True, font_color=SLATE)
    note = f(font_color=SLATE, text_wrap=True, valign="top")
    inp = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True, align="center")
    inp_l = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True)
    ok = f(bold=True, font_color=ACCENT)
    kpi = f(font_size=14, bold=True, font_color=ACCENT)

    ws_read = wb.add_worksheet("Read me")
    ws_in = wb.add_worksheet("Inputs")
    ws_tr = wb.add_worksheet("Tracker")
    ws_sc = wb.add_worksheet("Entry scenario")
    ws_ck = wb.add_worksheet("Checks")
    ws_pr = wb.add_worksheet("Products")
    ws_ci = wb.add_worksheet("Class index")
    ws_ls = wb.add_worksheet("Lists")
    for ws, colour in ((ws_read, SLATE), (ws_in, "#CA8A04"), (ws_tr, ACCENT), (ws_sc, ACCENT), (ws_ck, SLATE),
                       (ws_pr, "#94A3B8"), (ws_ci, "#94A3B8"), (ws_ls, "#94A3B8")):
        ws.set_tab_color(colour)
        ws.hide_gridlines(2)

    # ------------------------------------------------------------------ Lists
    ws_ls.write(0, 0, "Packs", h_left)
    for i, p in enumerate(products):
        ws_ls.write_string(i + 1, 0, p["label"])
    ws_ls.write(0, 2, "Compare with", h_left)
    for i, g in enumerate(group_names):
        ws_ls.write_string(i + 1, 2, g)
    ws_ls.write(0, 4, "Base year", h_left)
    for i, y in enumerate(YEARS[1:-1]):
        ws_ls.write_number(i + 1, 4, y)
    ws_ls.write(0, 6, "End year", h_left)
    for i, y in enumerate(YEARS[2:]):
        ws_ls.write_number(i + 1, 6, y)
    ws_ls.set_column(0, 0, 60)
    ws_ls.set_column(2, 6, 30)

    # ------------------------------------------------------------------ Products
    cols = ["Pack", "NDC", "Description", "Class", "Area", "Owner", "Family", "Medicaid units 2025",
            "Medicaid spend 2025", "Unit", "Latest rate"] + [str(y) for y in YEARS] + ["Change, base to end"]
    ws_pr.write_row(0, 0, cols, h_left)
    for j, y in enumerate(YEARS):
        ws_pr.write_number(0, 11 + j, y, h_left)  # numeric header so MATCH(year, header) works
    for i, p in enumerate(products, start=1):
        ws_pr.write_string(i, 0, p["label"])
        ws_pr.write_string(i, 1, p["ndc"])
        ws_pr.write_string(i, 2, p["description"])
        ws_pr.write_string(i, 3, p["segment"])
        ws_pr.write_string(i, 4, p["area"])
        ws_pr.write_string(i, 5, p["owner"])
        ws_pr.write_string(i, 6, p["family"])
        ws_pr.write_number(i, 7, p["units"], int0)
        ws_pr.write_number(i, 8, p["spend"], money)
        ws_pr.write_string(i, 9, p["unit"])
        ws_pr.write_number(i, 10, p["latest"], price)
        for j, y in enumerate(YEARS):
            v = p["prices"][y]
            if v is not None:
                ws_pr.write_number(i, 11 + j, v, price)
        r = i + 1
        rng = f"$L{r}:$Y{r}"
        b = f"INDEX({rng},MATCH(BaseYear,p_years,0))"
        e = f"INDEX({rng},MATCH(EndYear,p_years,0))"
        # rounded to 8 decimals so COUNTIF's number-to-text criterion compares exactly
        ws_pr.write_formula(i, 25, f'=IF(AND(ISNUMBER({b}),ISNUMBER({e})),ROUND({e}/{b}-1,8),"")', pct1)
    ws_pr.freeze_panes(1, 3)
    ws_pr.set_column(0, 0, 44)
    ws_pr.set_column(1, 1, 13)
    ws_pr.set_column(2, 2, 36)
    ws_pr.set_column(3, 6, 18)
    ws_pr.set_column(7, 25, 13)
    for nm, c in (("p_label", "A"), ("p_ndc", "B"), ("p_desc", "C"), ("p_segment", "D"), ("p_area", "E"), ("p_owner", "F"),
                  ("p_family", "G"), ("p_units", "H"), ("p_spend", "I"), ("p_unit", "J"), ("p_latest", "K"),
                  ("p_change", "Z")):
        wb.define_name(nm, f"=Products!${c}$2:${c}${last}")
    wb.define_name("p_prices", f"=Products!$L$2:$Y${last}")
    wb.define_name("p_years", "=Products!$L$1:$Y$1")

    # ------------------------------------------------------------------ Class index
    ws_ci.write(0, 0, "Year", h_left)
    for j, g in enumerate(group_names):
        ws_ci.write_string(0, 1 + j, g, h)
    for i, y in enumerate(YEARS, start=1):
        ws_ci.write_number(i, 0, y, cell_c)
        for j, g in enumerate(group_names):
            v = index[g][y]
            if v is not None:
                ws_ci.write_number(i, 1 + j, v, idx)
    ws_ci.set_column(0, 0, 8)
    ws_ci.set_column(1, len(group_names), 16)
    ws_ci.freeze_panes(1, 1)
    lastcol = chr(ord("A") + len(group_names))
    wb.define_name("c_years", f"='Class index'!$A$2:$A${len(YEARS) + 1}")
    wb.define_name("c_groups", f"='Class index'!$B$1:${lastcol}$1")
    wb.define_name("c_idx", f"='Class index'!$B$2:${lastcol}${len(YEARS) + 1}")

    # ------------------------------------------------------------------ Inputs
    ws_in.set_column(0, 0, 2)
    ws_in.set_column(1, 1, 38)
    ws_in.set_column(2, 2, 58)
    ws_in.set_column(3, 3, 60)
    ws_in.write("B1", "Price Tracker: inputs", title)
    ws_in.write("B2", "Change the yellow cells. Everything on the Tracker and Entry scenario sheets recalculates.", sub)
    ws_in.write("B4", "Pack (drug, strength, package)", label)
    ws_in.write_string("C4", scenarios[0]["product"], inp_l)
    ws_in.data_validation("C4", {"validate": "list", "source": f"=Lists!$A$2:$A${n + 1}"})
    wb.define_name("Product", "=Inputs!$C$4")
    ws_in.write("D4", f"{n} packs: the {N_PACKS} with the most 2025 Medicaid spend, plus the Merck headline packs", sub)
    ws_in.write("B5", "Compare with", label)
    ws_in.write_string("C5", scenarios[0]["compare"], inp)
    ws_in.data_validation("C5", {"validate": "list", "source": f"=Lists!$C$2:$C${len(group_names) + 1}"})
    wb.define_name("Compare", "=Inputs!$C$5")
    ws_in.write("D5", "a class or therapeutic area; its equal-weight price index is compared with the pack", sub)
    ws_in.write("B6", "Base year", label)
    ws_in.write_number("C6", scenarios[0]["base"], inp)
    ws_in.data_validation("C6", {"validate": "list", "source": f"=Lists!$E$2:$E${len(YEARS) - 1}"})
    wb.define_name("BaseYear", "=Inputs!$C$6")
    ws_in.write("B7", "End year", label)
    ws_in.write_number("C7", scenarios[0]["end"], inp)
    ws_in.data_validation("C7", {"validate": "list", "source": f"=Lists!$G$2:$G${len(YEARS)}"})
    wb.define_name("EndYear", "=Inputs!$C$7")
    ws_in.write("D7", "a year's rate is the average of its weekly NADAC rates (at least 20 weeks)", sub)
    ws_in.write("B9", "What if generics arrive? (cohort medians pre-filled)", h_left)
    ws_in.write("C9", "", h_left)
    for r, (lab, key, name, hint) in enumerate((
            ("Volume kept after 4 quarters (%)", "keep4", "Keep4", f"cohort median {cohort['spend_q4'] / cohort[('brand', 4)] * 100:.1f}: brand spend index / brand price index"),
            ("Volume kept after 8 quarters (%)", "keep8", "Keep8", f"cohort median {cohort['spend_q8'] / cohort[('brand', 8)] * 100:.1f}"),
            ("Brand price move after 4 quarters (%)", "move4", "Move4", f"cohort median {cohort[('brand', 4)] - 100:+.1f}"),
            ("Brand price move after 8 quarters (%)", "move8", "Move8", f"cohort median {cohort[('brand', 8)] - 100:+.1f}")), start=10):
        ws_in.write(r - 1, 1, lab, label)
        ws_in.write_number(r - 1, 2, scenarios[0][key], inp)
        wb.define_name(name, f"=Inputs!$C${r}")
        ws_in.write(r - 1, 3, hint, sub)
    ws_in.write("B15", "(helper) row of the pack on Products", label)
    ws_in.write_formula("C15", "=MATCH(Product,p_label,0)", f(bold=True, align="center"))
    wb.define_name("ProdRow", "=Inputs!$C$15")

    # ------------------------------------------------------------------ Tracker
    ws_tr.set_column(0, 0, 44)
    ws_tr.set_column(1, 6, 18)
    ws_tr.write("A1", "Price Tracker", title)
    ws_tr.write_formula("A2", '="NADAC rate per "&B9&", annual average of weekly rates. Data to ' + asof.isoformat() + '."', sub)
    ws_tr.write("A3", "Pack", h_left)
    ws_tr.write("B3", "", h_left)
    for r, lab, fm, fmt in (
            (4, "Description", "=INDEX(p_desc,ProdRow)", cell),
            (5, "NDC", "=INDEX(p_ndc,ProdRow)", cell),
            (6, "NADAC class", "=INDEX(p_segment,ProdRow)", cell),
            (7, "Therapeutic area", "=INDEX(p_area,ProdRow)", cell),
            (8, "Owner", "=INDEX(p_owner,ProdRow)", cell),
            (9, "Pricing unit", "=INDEX(p_unit,ProdRow)", cell)):
        ws_tr.write(r - 1, 0, lab, label)
        ws_tr.write_formula(r - 1, 1, fm, fmt)
    ws_tr.write("A10", "Move", h_left)
    ws_tr.write("B10", "", h_left)
    price_at = lambda y: f"INDEX(p_prices,ProdRow,MATCH({y},p_years,0))"
    ws_tr.write("A11", "Rate in base year", label)
    ws_tr.write_formula("B11", f'=IF(ISNUMBER({price_at("BaseYear")}),{price_at("BaseYear")},"n/a")', price)
    ws_tr.write("A12", "Rate in end year", label)
    ws_tr.write_formula("B12", f'=IF(ISNUMBER({price_at("EndYear")}),{price_at("EndYear")},"n/a")', price)
    ws_tr.write("A13", "Change, base to end", label)
    ws_tr.write_formula("B13", '=IF(AND(ISNUMBER(B11),ISNUMBER(B12)),B12/B11-1,"n/a")', pct1)
    ws_tr.write("A14", "Annual rate of change", label)
    ws_tr.write_formula("B14", '=IF(AND(ISNUMBER(B13),EndYear>BaseYear),(B12/B11)^(1/(EndYear-BaseYear))-1,"n/a")', pct1)
    ws_tr.write("A15", "Class", h_left)
    ws_tr.write("B15", "", h_left)
    cidx = lambda y: f"INDEX(c_idx,MATCH({y},c_years,0),MATCH(Compare,c_groups,0))"
    ws_tr.write("A16", "Class change, base to end (equal-weight index)", label)
    ws_tr.write_formula("B16", f'=IF(AND(ISNUMBER({cidx("BaseYear")}),ISNUMBER({cidx("EndYear")})),{cidx("EndYear")}/{cidx("BaseYear")}-1,"n/a")', pct1)
    ws_tr.write("A17", "Pack against class (percentage points)", label)
    ws_tr.write_formula("B17", '=IF(AND(ISNUMBER(B13),ISNUMBER(B16)),(B13-B16)*100,"n/a")', pp)
    ws_tr.write("A18", "Value and rank", h_left)
    ws_tr.write("B18", "", h_left)
    ws_tr.write("A19", "Medicaid units, 2025", label)
    ws_tr.write_formula("B19", "=INDEX(p_units,ProdRow)", int0)
    ws_tr.write("A20", "Annual value of the change at 2025 volume", label)
    ws_tr.write_formula("B20", '=IF(AND(ISNUMBER(B11),ISNUMBER(B12)),(B12-B11)*B19,"n/a")', money)
    ws_tr.write("A21", "Latest weekly rate", label)
    ws_tr.write_formula("B21", "=INDEX(p_latest,ProdRow)", price)
    ws_tr.write("A22", "Packs with both rates (of those listed)", label)
    ws_tr.write_formula("B22", "=COUNT(p_change)", int0)
    ws_tr.write("A23", "Share of those packs that moved less than this one", label)
    ws_tr.write_formula("B23", '=IF(AND(ISNUMBER(B13),B22>0),COUNTIF(p_change,"<"&ROUND(B13,8))/B22,"n/a")', pct1)
    ws_tr.write("A25", "Year by year", h_left)
    ws_tr.write_row("B25", ["Pack rate", "Pack year-on-year", "Class index", "Class year-on-year"], h)
    for i, y in enumerate(YEARS):
        r = 26 + i
        ws_tr.write_number(r - 1, 0, y, cell_c)
        ws_tr.write_formula(r - 1, 1, f'=IF(ISNUMBER(INDEX(p_prices,ProdRow,MATCH($A{r},p_years,0))),INDEX(p_prices,ProdRow,MATCH($A{r},p_years,0)),"")', price)
        if i == 0:
            ws_tr.write(r - 1, 2, "", cell)
            ws_tr.write(r - 1, 4, "", cell)
        else:
            ws_tr.write_formula(r - 1, 2, f'=IF(AND(ISNUMBER(B{r}),ISNUMBER(B{r - 1})),B{r}/B{r - 1}-1,"")', pct1)
            ws_tr.write_formula(r - 1, 4, f'=IF(AND(ISNUMBER(D{r}),ISNUMBER(D{r - 1})),D{r}/D{r - 1}-1,"")', pct1)
        ws_tr.write_formula(r - 1, 3, f'=IF(ISNUMBER(INDEX(c_idx,MATCH($A{r},c_years,0),MATCH(Compare,c_groups,0))),INDEX(c_idx,MATCH($A{r},c_years,0),MATCH(Compare,c_groups,0)),"")', idx)
    ws_tr.freeze_panes(3, 0)

    # ------------------------------------------------------------------ Entry scenario
    ws_sc.set_column(0, 0, 34)
    ws_sc.set_column(1, 5, 18)
    ws_sc.write("A1", "If generics arrive: an annual value, not a forecast", title)
    ws_sc.write("A2", "Starts from the pack's latest weekly NADAC rate and its 2025 Medicaid units. The price and volume moves are the yellow inputs.", sub)
    ws_sc.write("A4", "Pack", label)
    ws_sc.write_formula("B4", "=INDEX(p_desc,ProdRow)", cell)
    ws_sc.write("A5", "Latest weekly rate", label)
    ws_sc.write_formula("B5", "=INDEX(p_latest,ProdRow)", price)
    ws_sc.write("A6", "Medicaid units, 2025", label)
    ws_sc.write_formula("B6", "=INDEX(p_units,ProdRow)", int0)
    ws_sc.write_row("A8", ["", "Rate", "Units", "Annual value at NADAC rate", "Against today"], h)
    ws_sc.write("A9", "Today", label)
    ws_sc.write_formula("B9", "=B5", price)
    ws_sc.write_formula("C9", "=B6", int0)
    ws_sc.write_formula("D9", "=B9*C9", money)
    ws_sc.write_formula("E9", '=IF(D9>0,D9/D9,"n/a")', pct1)
    ws_sc.write("A10", "After 4 quarters", label)
    ws_sc.write_formula("B10", "=B5*(1+Move4/100)", price)
    ws_sc.write_formula("C10", "=B6*Keep4/100", int0)
    ws_sc.write_formula("D10", "=B10*C10", money)
    ws_sc.write_formula("E10", '=IF(D9>0,D10/D9,"n/a")', pct1)
    ws_sc.write("A11", "After 8 quarters", label)
    ws_sc.write_formula("B11", "=B5*(1+Move8/100)", price)
    ws_sc.write_formula("C11", "=B6*Keep8/100", int0)
    ws_sc.write_formula("D11", "=B11*C11", money)
    ws_sc.write_formula("E11", '=IF(D9>0,D11/D9,"n/a")', pct1)
    ws_sc.write("A13", "Reference: what the 48 generic-entry events in Rx Market Pulse show", h_left)
    ws_sc.write_row("B13", ["Quarters after entry", "", "", ""], h_left)
    ws_sc.write_row("A14", ["Median", "0", "4", "8", "12"], h)
    ref = [("Brand NADAC price index (before entry = 100)", [cohort[("brand", k)] for k in (0, 4, 8, 12)]),
           ("Generic NADAC price index (launch price = 100)", [cohort[("generic", k)] for k in (0, 4, 8, 12)]),
           ("Brand Medicaid spend index (year before entry = 100)", [None, cohort["spend_q4"], cohort["spend_q8"], None])]
    for i, (lab, vals) in enumerate(ref):
        ws_sc.write(14 + i, 0, lab, cell)
        for j, v in enumerate(vals):
            if v is None:
                ws_sc.write(14 + i, 1 + j, "", cell)
            else:
                ws_sc.write_number(14 + i, 1 + j, v, idx)
    ws_sc.write("A19", "These are medians across molecules, not a prediction for any one product. Each pack is its own case.", note)

    # ------------------------------------------------------------------ Checks
    ws_ck.set_column(0, 0, 3)
    ws_ck.set_column(1, 1, 60)
    ws_ck.set_column(2, 3, 22)
    ws_ck.set_column(4, 4, 12)
    ws_ck.write("B1", "Checks", title)
    ws_ck.write_row("B4", ["Check", "Value", "Rule", "Result"], h_left)
    total_spend = sum(p["spend"] for p in products)
    checks = [
        ("The chosen pack is on the Products sheet", "=ProdRow", "a row number", '=IF(ISNUMBER(C5),"OK","CHECK")'),
        ("Base year is before end year", '=BaseYear&" < "&EndYear', "base < end", '=IF(BaseYear<EndYear,"OK","CHECK")'),
        ("The pack has a rate in both years", "=IF(AND(ISNUMBER(Tracker!B11),ISNUMBER(Tracker!B12)),\"yes\",\"no\")", "yes", '=IF(C7="yes","OK","CHECK")'),
        ("The class has an index in both years", "=IF(ISNUMBER(Tracker!B16),\"yes\",\"no\")", "yes", '=IF(C8="yes","OK","CHECK")'),
        ("Volume kept is between 0 and 100", '=Keep4&" / "&Keep8', "0 to 100", '=IF(AND(Keep4>=0,Keep4<=100,Keep8>=0,Keep8<=100),"OK","CHECK")'),
        ("Products sheet still holds every pack and its 2025 spend", "=SUM(p_spend)", f"{total_spend:,.0f}", f'=IF(AND(COUNTA(p_label)={n},ABS(C10-{total_spend!r})<1),"OK","CHECK")'),
    ]
    for i, (lab, val, rule, res) in enumerate(checks):
        r = 5 + i
        ws_ck.write(r - 1, 1, lab, cell)
        ws_ck.write_formula(r - 1, 2, val, cell_c)
        ws_ck.write(r - 1, 3, rule, cell_c)
        ws_ck.write_formula(r - 1, 4, res, f(bold=True, align="center", bottom=1, bottom_color=RULE))
    ws_ck.write("B12", "Overall", f(bold=True, top=2, top_color=INK))
    ws_ck.write_formula("E12", '=IF(COUNTIF(E5:E10,"OK")=ROWS(E5:E10),"ALL OK","CHECK")', f(bold=True, align="center", top=2, top_color=INK, font_color=ACCENT))

    # ------------------------------------------------------------------ Read me
    ws_read.set_column(0, 0, 2)
    ws_read.set_column(1, 1, 110)
    ws_read.write("B1", "Price Tracker", title)
    ws_read.write("B2", "Part of Drug Price Watch: weekly pharmacy drug prices (NADAC) from CMS, 2013 to " + asof.isoformat(), sub)
    lines = [
        ("What it answers", "How has this pack's price moved between two years, how did its class move, and what would an annual value look like if generics arrived?"),
        ("Inputs", "Yellow cells on Inputs: the pack, the class to compare with, base and end year, and four what-if numbers (pre-filled with the medians found in this project)."),
        ("Tracker", "Live formulas only. A year's rate is the average of the pack's weekly NADAC rates that year (at least 20 weeks). The class index is the equal-weight chained index from the pipeline, averaged by year."),
        ("Share of packs that moved less", "Among the packs listed on Products with a rate in both years, the share whose change was smaller than this pack's."),
        ("Entry scenario", "Latest weekly rate x 2025 Medicaid units = an annual value at NADAC rates. The scenario applies the price and volume moves you choose. It is arithmetic on assumptions, not a forecast."),
        ("Not in this workbook", "Rebates and net price (NADAC is what pharmacies paid, before rebates); clinic-administered products such as Keytruda; anything after the data date."),
        ("Checks", "Six formulas that go to CHECK if an input is invalid or the Products sheet is edited."),
        ("Sources", "NADAC weekly rates (CMS, data.medicaid.gov); Medicaid units and spend (State Drug Utilization Data, via Rx Market Pulse). github.com/f20230125-sudo/drug-price-watch"),
    ]
    for i, (a, b) in enumerate(lines):
        ws_read.write(3 + 2 * i, 1, a, label)
        ws_read.write(4 + 2 * i, 1, b, note)
        ws_read.set_row(4 + 2 * i, 30)
    ws_read.activate()
    wb.close()
    return path


def main() -> int:
    p = build()
    print(f"wrote {p} ({p.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
