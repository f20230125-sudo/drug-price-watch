"""Data tests on the built warehouse (skipped when it has not been built): the numbers tie back to the sources."""

from __future__ import annotations

import json

import pytest

from pw import dq
from pw.sources import MARTS, RAW

pytestmark = pytest.mark.usefixtures("real")


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_rows_loaded_equal_rows_the_portal_reports_for_every_year(real):
    expected = json.loads((RAW / "expected_rows.json").read_text())
    got = dict(real.execute("select source_year, count(*) from stg_nadac group by 1").fetchall())
    assert len(got) == 14
    for year, n in got.items():
        assert n == expected[f"nadac_{year}"], year


def test_every_staged_row_is_in_the_facts_or_in_quarantine(real):
    assert one(real, "select count(*) from stg_nadac") == (
        one(real, "select count(*) from fact_nadac") + one(real, "select count(*) from quarantine_nadac"))


def test_one_price_per_pack_per_week(real):
    assert one(real, "select count(*) from (select ndc11, as_of from fact_nadac group by 1, 2 having count(*) > 1)") == 0


def test_all_prices_positive_and_ndcs_eleven_digits(real):
    assert one(real, "select count(*) from fact_nadac where price <= 0") == 0
    assert one(real, "select count(*) from fact_nadac where not regexp_matches(ndc11, '^[0-9]{11}$')") == 0


def test_weekly_snapshots_are_consecutive(real):
    bad = one(real, """select count(*) from (select date_diff('day', lag(d) over (order by d), d) g
                       from (select distinct as_of d from fact_nadac)) where g not in (6, 7, 8)""")
    assert bad == 0


def test_segments_partition_the_facts(real):
    n = one(real, "select count(*) from fact_nadac")
    by = one(real, "select sum(c) from (select count(*) c from fact_nadac group by segment)")
    assert n == by
    assert {s for (s,) in real.execute("select distinct segment from fact_nadac").fetchall()} == {
        "Brand", "Generic", "Branded generic", "Biologic"}


def test_index_starts_at_one_hundred(real):
    w = one(real, "select weighted from mart_index_week where kind='segment' and grp='All' and as_of = date '2019-01-02'")
    assert w == pytest.approx(100.0)
    e = one(real, "select equal_weight from mart_index_week where kind='segment' and grp='All' order by as_of limit 1")
    assert e == pytest.approx(100.0)


def test_weighted_index_has_no_gaps_since_2019(real):
    n = one(real, "select count(*) from mart_index_week where kind='segment' and grp='All' and as_of >= date '2019-01-02' and weighted is null")
    assert n == 0


def test_chained_index_equals_the_product_of_weekly_ratios(real):
    prod = one(real, """select exp(sum(ln(ratio_w))) from idx_week_ratio
                        where kind='segment' and grp='All' and as_of > date '2019-01-02'""")
    last = one(real, "select weighted from mart_index_week where kind='segment' and grp='All' order by as_of desc limit 1")
    assert last == pytest.approx(100 * prod, rel=1e-9)


def test_weekly_ratio_matches_an_independent_python_recomputation(real):
    from datetime import date
    for wk in (date(2021, 6, 16), date(2023, 11, 15), date(2026, 9, 23)):
        sql_r = one(real, f"select ratio_w from idx_week_ratio where kind='segment' and grp='All' and as_of = date '{wk}'")
        assert sql_r == pytest.approx(dq.independent_ratio(real, wk), rel=1e-12)


def test_change_counts_add_up(real):
    assert one(real, "select count(*) from fact_change") == one(real, "select sum(changes) from mart_events_year")


def test_january_is_the_busiest_month_for_brand_price_steps(real):
    rows = dict(real.execute("select m, steps_up_2pct from mart_events_season where segment = 'Brand'").fetchall())
    assert max(rows, key=rows.get) == 1
    assert rows[1] / sum(rows.values()) > 0.3


def test_erosion_brand_index_is_one_hundred_the_quarter_before_entry(real):
    bad = one(real, "select count(*) from mart_erosion_price where side='brand' and k = -1 and abs(price_index - 100) > 1e-9")
    assert bad == 0


def test_every_erosion_event_comes_from_rx_market_pulse(real):
    assert one(real, "select count(*) from rx_events") == 48
    assert one(real, "select count(distinct ingredient) from mart_erosion_events_price") == 48


def test_triangulation_effects_reconcile_on_a_pair(real):
    # recompute NADAC's 2022-25 effect for brands from the raw tables, with no SQL macros shared with the mart
    rows = real.execute("""
        select n0.p, n1.p, u1.units, u0.units, u0.spend, u1.spend
        from (select ndc11, avg(price) p from fact_nadac where year(as_of) = 2022 group by 1 having count(*) >= 20) n0
        join (select ndc11, avg(price) p from fact_nadac where year(as_of) = 2025 group by 1 having count(*) >= 20) n1 using (ndc11)
        join rx_units u0 on u0.ndc11 = n0.ndc11 and u0.year = 2022 and u0.units > 0 and u0.spend > 0
        join rx_units u1 on u1.ndc11 = n0.ndc11 and u1.year = 2025 and u1.units > 0 and u1.spend > 0
        join dim_ndc d on d.ndc11 = n0.ndc11 where d.segment = 'Brand'""").fetchall()
    effect = sum((p1 - p0) * q1 for p0, p1, q1, q0, s0, s1 in rows
                 if 0.1 <= p1 / p0 <= 10 and 0.1 <= (s1 / q1) / (s0 / q0) <= 10)
    stored = one(real, "select nadac_effect from mart_triangulation where y0 = 2022 and y1 = 2025 and segment = 'Brand'")
    assert stored == pytest.approx(effect, rel=1e-9)


def test_scorecard_has_no_failures(real):
    checks = dq.run(real)
    assert len(checks) >= 20
    assert [c.id for c in checks if c.status == "fail"] == []


def test_headline_numbers_come_from_the_marts(real):
    from pw.sources import ROOT
    head = json.loads((ROOT / "dashboard" / "public" / "data" / "headline.json").read_text())
    last = one(real, "select weighted from mart_index_month where kind='segment' and grp='Brand' order by month desc limit 1")
    assert head["index"]["weighted"]["brand"] == pytest.approx(last, abs=0.01)
    assert head["packs"] == one(real, "select count(distinct ndc11) from fact_nadac")
    assert head["checks"]["total"] == len(list(open(MARTS / "dq_checks.csv", encoding="utf-8"))) - 1
