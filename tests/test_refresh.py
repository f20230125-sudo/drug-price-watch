"""The weekly watch, run on a small NADAC-shaped file written for the test."""

from __future__ import annotations

import csv
from datetime import date, timedelta

import pytest

from pw import refresh

HEADER = ["NDC Description", "NDC", "NADAC Per Unit", "Effective Date", "Pricing Unit", "Pharmacy Type Indicator", "OTC",
          "Explanation Code", "Classification for Rate Setting", "Corresponding Generic Drug NADAC Per Unit",
          "Corresponding Generic Drug Effective Date", "As of Date"]
WATCHES = [
    {"name": "Generic sitagliptin packs", "kind": "presence", "pattern": "SITAGLIPTIN", "class": "G", "why": "test"},
    {"name": "Januvia 100 mg rate", "kind": "rate", "pattern": "^JANUVIA 100 MG TABLET$", "class": "B", "why": "test"},
]


def mdy(d: date) -> str:
    return d.strftime("%m/%d/%Y")


def write(path, weeks, packs, bulk_week=None, bulk_pack_count=0, extra=()):
    """packs: list of (ndc, description, cls, price). In the bulk week every pack moves by +2%; Januvia moves -10%."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        for wk in weeks:
            for ndc, desc, cls, price in packs:
                p = price
                if bulk_week and wk >= bulk_week:
                    p = price * (0.9 if desc.startswith("JANUVIA") else 1.02)
                w.writerow([desc, ndc, f"{p:.5f}", mdy(wk), "EA", "C/I", "N", "1", cls, "", "", mdy(wk)])
        for row in extra:
            w.writerow(row)


@pytest.fixture()
def file(tmp_path):
    today = date(2026, 10, 16)
    weeks = [date(2026, 8, 5) + timedelta(days=7 * i) for i in range(10)]  # last one 2026-10-07
    packs = [(f"{i:011d}", f"DRUG{i} 10 MG TAB", "G", 1.0 + i / 100) for i in range(1, 1201)]
    packs += [("00006027731", "JANUVIA 100 MG TABLET", "B", 10.5)]
    p = tmp_path / "nadac_2026.csv"
    write(p, weeks, packs, bulk_week=weeks[6])
    return p, today, len(weeks) * len(packs)


def test_a_clean_file_passes_every_check(file):
    p, today, n = file
    rep = refresh.analyse(p, n, WATCHES, today)
    assert rep["status"] == "ok"
    assert all(c["ok"] for c in rep["checks"])
    assert rep["rows"] == n and rep["packs"] == 1201 and rep["weeksInFile"] == 10


def test_the_latest_bulk_update_is_counted(file):
    p, today, n = file
    u = refresh.analyse(p, n, WATCHES, today)["latestUpdate"]
    assert u["date"] == "2026-09-16"
    assert u["changes"] == 1201 and u["ups"] == 1200 and u["downs"] == 1
    assert u["material"] == 1201  # +2% and -10% are both 1% or more


def test_a_row_count_that_differs_from_the_portal_fails(file):
    p, today, n = file
    rep = refresh.analyse(p, n + 1, WATCHES, today)
    assert rep["status"] == "FAILED"
    assert [c["name"] for c in rep["checks"] if not c["ok"]] == ["Rows equal the portal's row count"]


def test_a_stale_file_fails_the_freshness_check(file):
    p, today, n = file
    rep = refresh.analyse(p, n, WATCHES, today + timedelta(days=30))
    assert rep["status"] == "FAILED"
    assert any(c["name"].startswith("Newest snapshot") and not c["ok"] for c in rep["checks"])


def test_a_bad_price_and_a_bad_ndc_are_caught(tmp_path):
    p = tmp_path / "bad.csv"
    wk = date(2026, 10, 7)
    write(p, [wk - timedelta(days=7), wk], [("00000000001", "A 1 MG TAB", "G", 1.0)],
          extra=[["B 1 MG TAB", "123", "0", mdy(wk), "EA", "C/I", "N", "1", "G", "", "", mdy(wk)]])
    rep = refresh.analyse(p, None, [], date(2026, 10, 16))
    failed = {c["name"] for c in rep["checks"] if not c["ok"]}
    assert failed == {"Every NDC has 11 digits", "Every price is a positive number"}


def test_the_presence_watch_flags_a_change_in_the_number_of_generic_packs_since_the_last_run(file, tmp_path):
    p, today, n = file
    first = refresh.analyse(p, n, WATCHES, today)
    assert first["watches"][0]["found"] == 0 and not first["watches"][0]["flag"]  # nothing to compare with, nothing found
    wk = date(2026, 10, 7)
    extra = [["SITAGLIPTIN 100 MG TABLET", "99999999999", "1.5", mdy(wk), "EA", "C/I", "N", "1", "G", "", "", mdy(wk)]]
    q = tmp_path / "with_generic.csv"
    q.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    with q.open("a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(extra)
    again = refresh.analyse(q, n + 1, WATCHES, today, previous=first)
    w = again["watches"][0]
    assert w["flag"] and w["found"] == 1 and w["previous"] == 0 and w["packs"] == ["SITAGLIPTIN 100 MG TABLET"]
    assert "Generic sitagliptin packs" in again["flags"]
    same = refresh.analyse(q, n + 1, WATCHES, today, previous=again)
    assert not same["watches"][0]["flag"]  # unchanged since the last run


def test_a_brand_pack_does_not_trigger_the_generic_watch(file):
    p, today, n = file
    rep = refresh.analyse(p, n, WATCHES, today)
    assert rep["watches"][0]["found"] == 0


def test_the_rate_watch_flags_a_move_of_five_percent_or_more(file):
    p, today, n = file
    rep = refresh.analyse(p, n, WATCHES, today)
    w = rep["watches"][1]
    assert w["flag"]
    assert w["moves"][0]["pack"] == "JANUVIA 100 MG TABLET" and w["moves"][0]["pct"] == pytest.approx(-0.1, abs=1e-4)


def test_log_and_json_are_written(file, tmp_path, monkeypatch):
    p, today, n = file
    monkeypatch.setattr(refresh, "WATCH_JSON", tmp_path / "watch.json")
    monkeypatch.setattr(refresh, "LOG", tmp_path / "log.csv")
    monkeypatch.setattr(refresh, "SITE_COPY", tmp_path / "none" / "watch.json")
    rep = refresh.analyse(p, n, WATCHES, today)
    refresh.write(rep)
    refresh.write(rep)
    rows = list(csv.DictReader((tmp_path / "log.csv").open(encoding="utf-8")))
    assert len(rows) == 2 and rows[0]["status"] == "ok" and rows[0]["latest_update"] == "2026-09-16"
    assert (tmp_path / "watch.json").exists()


def test_the_presence_watch_counts_packs_not_descriptions(tmp_path):
    """Three packs that share one description are three packs (28 generic sitagliptin packs share five descriptions)."""
    wk = date(2026, 10, 7)
    p = tmp_path / "share.csv"
    write(p, [wk - timedelta(days=7), wk], [(f"{i:011d}", "SITAGLIPTIN PHOSPHATE 100 MG TABLET", "G", 3.77) for i in range(1, 4)])
    rep = refresh.analyse(p, None, WATCHES[:1], date(2026, 10, 16))
    assert rep["watches"][0]["found"] == 3
    assert rep["watches"][0]["packs"] == ["SITAGLIPTIN PHOSPHATE 100 MG TABLET"]
