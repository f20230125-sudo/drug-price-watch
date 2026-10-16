"""The price index and the change events, checked against numbers worked out by hand on a tiny dataset.

Two packs, A (generic, 100 Medicaid units in 2019) and B (brand, 10 units), priced weekly from 2018-12-26:

    week        A     B      weighted ratio                       index (base 100 at 2019-01-02)
    2019-01-02  1.00  10     (100*1.0 + 10*10) / (100*1.0 + 10*10) = 1        100
    2019-01-09  1.10  10     (110 + 100) / (100 + 100)             = 1.05     105
    2019-01-16  1.10  11     (110 + 110) / (110 + 100)             = 1.0476   110
    2019-01-23  1.21  11     (121 + 110) / (110 + 110)             = 1.05     115.5
"""

from __future__ import annotations

import math

import pytest

from conftest import build_tiny, row

WEEKS = ["2018-12-26", "2019-01-02", "2019-01-09", "2019-01-16", "2019-01-23"]
A_PRICES = ["1.00", "1.00", "1.10", "1.10", "1.21"]
B_PRICES = ["10", "10", "10", "11", "11"]
ATTRS = [("00000000001", "Generic", "A-FAMILY", "ALPHA", None, "Cardiovascular", False),
         ("00000000002", "Brand", "B-FAMILY", "BETA", "Merck (MSD)", "Diabetes & obesity", False)]
UNITS = [("00000000001", 2019, 100.0, 10.0, 100.0), ("00000000002", 2019, 10.0, 1.0, 100.0)]


def base_rows():
    rows, rid = [], 0
    for w, a, b in zip(WEEKS, A_PRICES, B_PRICES):
        rid += 1
        rows.append(row(rid, "00000000001", w, a, "G", "ALPHA 10 MG TAB"))
        rid += 1
        rows.append(row(rid, "00000000002", w, b, "B", "BETA 20 MG TAB"))
    return rows


@pytest.fixture()
def tiny(tmp_path):
    return build_tiny(tmp_path, base_rows(), ATTRS, UNITS)


def series(con, grp, col):
    return {d.isoformat(): v for d, v in con.execute(
        f"select as_of, {col} from mart_index_week where kind = 'segment' and grp = ? order by as_of", [grp]).fetchall()}


def test_weighted_all_market_index_matches_hand_calculation(tiny):
    s = series(tiny, "All", "weighted")
    assert s["2019-01-02"] == pytest.approx(100.0)
    assert s["2019-01-09"] == pytest.approx(105.0)
    assert s["2019-01-16"] == pytest.approx(110.0)
    assert s["2019-01-23"] == pytest.approx(115.5)


def test_segment_indexes_move_only_with_their_own_packs(tiny):
    brand, generic = series(tiny, "Brand", "weighted"), series(tiny, "Generic", "weighted")
    assert [round(brand[w], 6) for w in WEEKS[1:]] == [100.0, 100.0, 110.0, 110.0]
    assert [round(generic[w], 6) for w in WEEKS[1:]] == [100.0, 110.0, 110.0, 121.0]


def test_equal_weight_index_is_a_geometric_mean(tiny):
    s = series(tiny, "All", "equal_weight")
    root = math.sqrt(1.1)  # in each of the three moving weeks exactly one of the two packs rises 10%
    assert s["2019-01-02"] == pytest.approx(100.0)
    assert s["2019-01-09"] == pytest.approx(100 * root)
    assert s["2019-01-16"] == pytest.approx(100 * root**2)
    assert s["2019-01-23"] == pytest.approx(100 * root**3)


def test_therapeutic_area_and_family_indexes_exist_only_for_classified_packs(tiny):
    area = tiny.execute("select grp from mart_index_week where kind = 'area' group by grp order by grp").fetchall()
    assert area == [("Cardiovascular",), ("Diabetes & obesity",)]
    fam = tiny.execute("select grp from mart_index_week where kind = 'family' group by grp").fetchall()
    assert fam == [("B-FAMILY",)]  # only Merck-owned families get a family index


def test_extreme_relative_is_excluded_from_index_and_counted(tmp_path):
    rows = base_rows()
    rid = 100
    for w, p in zip(WEEKS, ["1.0", "1.0", "1.0", "20.0", "20.0"]):  # 20x jump in the week of 2019-01-16
        rid += 1
        rows.append(row(rid, "00000000003", w, p, "G", "GAMMA 5 MG TAB"))
    attrs = ATTRS + [("00000000003", "Generic", "G-FAMILY", "GAMMA", None, "Cardiovascular", False)]
    units = UNITS + [("00000000003", 2019, 50.0, 5.0, 50.0)]
    con = build_tiny(tmp_path, rows, attrs, units)
    s = series(con, "All", "weighted")
    # Pack C (50 units, flat at 1.0) joins A and B in the first weeks: 2019-01-09 is (110+100+50)/(100+100+50) = 1.04.
    # In the week of its 20x jump it is left out of numerator and denominator, so only A and B count:
    # (110+110)/(110+100) = 220/210. Index = 100 x 1.04 x 220/210.
    assert s["2019-01-09"] == pytest.approx(104.0)
    assert s["2019-01-16"] == pytest.approx(100 * 1.04 * 220 / 210)
    n_ext = con.execute("select n_extreme from mart_index_week where kind='segment' and grp='All' and as_of = date '2019-01-16'").fetchone()[0]
    assert n_ext == 1


def test_a_missing_week_stops_a_pack_being_compared_across_the_gap(tmp_path):
    rows = base_rows()
    rid = 100
    for w, p in zip(WEEKS, ["5", "5", None, "6", "6"]):  # not priced on 2019-01-09
        if p is None:
            continue
        rid += 1
        rows.append(row(rid, "00000000004", w, p, "G", "DELTA 1 MG TAB"))
    con = build_tiny(tmp_path, rows, ATTRS, UNITS)
    n = con.execute("select n_matched from mart_index_week where kind='segment' and grp='All' and as_of = date '2019-01-16'").fetchone()[0]
    assert n == 2  # A and B only: D's previous price is 14 days old
    n2 = con.execute("select n_matched from mart_index_week where kind='segment' and grp='All' and as_of = date '2019-01-23'").fetchone()[0]
    assert n2 == 3  # D is compared again from the following week


def test_pack_without_medicaid_units_counts_in_equal_weight_only(tmp_path):
    rows = base_rows()
    rid = 100
    for w, p in zip(WEEKS, ["2", "2", "2", "2", "4"]):
        rid += 1
        rows.append(row(rid, "00000000005", w, p, "G", "EPSILON 2 MG TAB"))
    con = build_tiny(tmp_path, rows, ATTRS, UNITS)
    assert series(con, "All", "weighted")["2019-01-23"] == pytest.approx(115.5)  # unchanged
    r = con.execute("select n_matched, n_weighted from mart_index_week where kind='segment' and grp='All' and as_of = date '2019-01-23'").fetchone()
    assert r == (3, 2)
    assert series(con, "All", "equal_weight")["2019-01-23"] != pytest.approx(100 * math.sqrt(1.1) ** 3)


def test_change_events_are_the_weeks_a_price_differs_from_the_week_before(tiny):
    got = tiny.execute("select ndc11, as_of, round(pct, 6) from fact_change order by ndc11, as_of").fetchall()
    assert [(n, d.isoformat(), p) for n, d, p in got] == [
        ("00000000001", "2019-01-09", 0.1), ("00000000001", "2019-01-23", 0.1), ("00000000002", "2019-01-16", 0.1)]


def test_annual_impact_is_price_change_times_medicaid_units(tiny):
    v = tiny.execute("select annual_impact from fact_change where ndc11 = '00000000002'").fetchone()[0]
    assert v == pytest.approx((11 - 10) * 10.0)


def test_events_by_year_counts_material_changes(tiny):
    r = tiny.execute("select changes, material_changes, ups, downs from mart_events_year where y = 2019 and segment = 'Generic'").fetchone()
    assert r == (2, 2, 2, 0)
