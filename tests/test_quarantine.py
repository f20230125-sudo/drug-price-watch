"""Rows that break a rule are set aside with a reason and never reach the facts."""

from __future__ import annotations

import pytest

from conftest import build_tiny, row

ATTRS = [("11111111111", "Generic", "X", "ALPHA", None, "Cardiovascular", False)]
UNITS = [("11111111111", 2019, 10.0, 1.0, 10.0)]


@pytest.fixture()
def con(tmp_path):
    rows = [
        row(1, "11111111111", "2019-01-02", "1.00"),                    # good
        row(2, "11111111111", "2019-01-09", "1.10"),                    # good
        row(3, "123", "2019-01-02", "1.00"),                            # NDC too short
        row(4, "2222222222A", "2019-01-02", "1.00"),                    # NDC not digits
        row(5, "33333333333", "2019-01-02", "0"),                       # zero price
        row(6, "44444444444", "2019-01-02", "-1.5"),                    # negative price
        row(7, "55555555555", "2019-01-02", "abc"),                     # price not a number
        row(8, "66666666666", "2019-01-02", "1.0", cls="X"),            # unknown class
        row(9, "77777777777", "2019-01-02", "1.0", cls="B-BIO"),        # a real class NADAC added in 2022
        row(10, "88888888888", "2019-01-02", "1.0"),                    # duplicated below
        row(11, "88888888888", "2019-01-02", "1.2"),
    ]
    bad_date = list(row(12, "99999999999", "2019-01-02", "1.0"))
    bad_date[11] = "13/45/2019"
    rows.append(tuple(bad_date))
    return build_tiny(tmp_path, rows, ATTRS, UNITS, layers=("02_quarantine.sql", "03_model.sql"))


def reasons(con):
    return dict(con.execute("select rid, reason from quarantine_nadac").fetchall())


def test_each_broken_rule_names_its_reason(con):
    r = reasons(con)
    assert r[3] == "NDC is not 11 digits"
    assert r[4] == "NDC is not 11 digits"
    assert r[5] == "price is zero or negative"
    assert r[6] == "price is zero or negative"
    assert r[7] == "price is not a number"
    assert r[8] == "unknown rate-setting class"
    assert r[12] == "as-of date cannot be read"


def test_one_of_two_rows_for_the_same_pack_and_week_is_set_aside(con):
    r = reasons(con)
    assert sorted(v for k, v in r.items() if k in (10, 11)) == ["same NDC twice in one week"]
    assert 11 in r and 10 not in r  # same effective date: the first row is kept, the second is set aside
    kept = con.execute("select price from fact_nadac where ndc11 = '88888888888'").fetchall()
    assert kept == [(1.0,)]


def test_good_rows_reach_the_facts_and_bad_ones_do_not(con):
    in_fact = {n for (n,) in con.execute("select ndc11 from fact_nadac").fetchall()}
    assert in_fact == {"11111111111", "77777777777", "88888888888"}


def test_every_staged_row_is_either_in_the_facts_or_in_quarantine(con):
    staged = con.execute("select count(*) from stg_nadac").fetchone()[0]
    fact = con.execute("select count(*) from fact_nadac").fetchone()[0]
    quarantined = con.execute("select count(*) from quarantine_nadac").fetchone()[0]
    assert fact + quarantined == staged


def test_biologic_class_is_accepted_as_its_own_segment(con):
    assert con.execute("select segment from fact_nadac where ndc11 = '77777777777'").fetchone() == ("Biologic",)
