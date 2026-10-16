"""Shared test helpers.

`tiny_warehouse` builds a hand-sized NADAC dataset in an in-memory DuckDB and runs the project's real SQL files over
it, so the index, event and quarantine logic is checked against numbers worked out by hand. `real` opens the built
warehouse (data/warehouse/pw.duckdb) read-only and skips the data tests when it has not been built.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pw.sources import WAREHOUSE  # noqa: E402

SQL = ROOT / "sql"
STG_COLS = ["rid", "source_year", "ndc_description", "ndc", "nadac_per_unit", "effective_date", "pricing_unit",
            "pharmacy_type_indicator", "otc", "explanation_code", "classification_for_rate_setting", "as_of_date",
            "generic_nadac_per_unit", "generic_effective_date"]


def mdy(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{m}/{d}/{y}"


def row(rid: int, ndc: str, iso_week: str, price: str, cls: str = "G", name: str = "TEST DRUG 10 MG TAB") -> tuple:
    return (rid, int(iso_week[:4]), name, ndc, price, mdy(iso_week), "EA", "C/I", "N", "1", cls, mdy(iso_week), None, None)


def run_sql(con: duckdb.DuckDBPyConnection, name: str, **params: str) -> None:
    sql = (SQL / name).read_text(encoding="utf-8")
    for k, v in params.items():
        sql = sql.replace("{" + k + "}", v)
    con.execute(sql)


def write_ref(ref: Path, attrs: list[tuple], units: list[tuple]) -> None:
    ref.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("create table a (ndc11 varchar, market_class varchar, family varchar, ingredient varchar, owner varchar, "
                "area varchar, is_biologic boolean)")
    con.executemany("insert into a values (?,?,?,?,?,?,?)", attrs)
    con.execute(f"copy a to '{(ref / 'rx_ndc_attrs.csv.gz').as_posix()}' (header, delimiter ',')")
    con.execute("create table u (ndc11 varchar, year integer, units double, rx double, spend double)")
    con.executemany("insert into u values (?,?,?,?,?)", units)
    con.execute(f"copy u to '{(ref / 'rx_units_year.csv.gz').as_posix()}' (header, delimiter ',')")


def build_tiny(tmp_path: Path, rows: list[tuple], attrs: list[tuple], units: list[tuple],
               layers: tuple[str, ...] = ("02_quarantine.sql", "03_model.sql", "04_marts_index.sql", "05_marts_events.sql")):
    ref, marts = tmp_path / "ref", tmp_path / "marts"
    marts.mkdir(exist_ok=True)
    write_ref(ref, attrs, units)
    con = duckdb.connect()
    con.execute("create table stg_nadac (" + ", ".join(
        f"{c} {'integer' if c in ('rid', 'source_year') else 'varchar'}" for c in STG_COLS) + ")")
    con.executemany("insert into stg_nadac values (" + ",".join("?" * len(STG_COLS)) + ")", rows)
    for name in layers:
        run_sql(con, name, ref_dir=ref.as_posix(), marts_dir=marts.as_posix())
    return con


@pytest.fixture(scope="session")
def real():
    if not WAREHOUSE.exists():
        pytest.skip("warehouse not built: run python -m pw.fetch && python -m pw.build")
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    yield con
    con.close()
