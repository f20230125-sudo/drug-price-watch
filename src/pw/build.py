"""Build the DuckDB warehouse from data/raw.

    python -m pw.build              # stage -> model -> marts
    python -m pw.build stage        # only the staging layer
    python -m pw.build model marts  # re-run later layers on an existing staging layer

Layers (each is a numbered SQL file in sql/, run in order):
    01     staging: NADAC as published, every column text, nothing removed
    02     typed copy and quarantine: rows that break a rule go to a table of their own, with the reason
    03     facts and dimensions: one price per NDC per week, one row per NDC
    04+    marts: small tables the dashboard, workbook and report read
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb

from .sources import MARTS, RAW, REF, ROOT, WAREHOUSE

SQL_DIR = ROOT / "sql"


def connect(path: Path = WAREHOUSE, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def _run_sql(con: duckdb.DuckDBPyConnection, name: str, **params: str) -> None:
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    for key, value in params.items():
        sql = sql.replace("{" + key + "}", value)
    started = time.time()
    con.execute(sql)
    print(f"  {name:<28} {time.time() - started:5.1f}s", flush=True)


def stage(con: duckdb.DuckDBPyConnection) -> None:
    print("stage")
    files = sorted(RAW.glob("nadac_[0-9][0-9][0-9][0-9].csv"))
    if not files:
        raise SystemExit("no nadac_YYYY.csv in data/raw: run python -m pw.fetch first")
    listed = "[" + ", ".join("'" + p.as_posix() + "'" for p in files) + "]"
    _run_sql(con, "01_stage_nadac.sql", files=listed)


def model(con: duckdb.DuckDBPyConnection) -> None:
    print("model")
    for name in sorted(p.name for p in SQL_DIR.glob("0[2-3]*.sql")):
        _run_sql(con, name, ref_dir=REF.as_posix())


def marts(con: duckdb.DuckDBPyConnection) -> None:
    print("marts")
    MARTS.mkdir(parents=True, exist_ok=True)
    for name in sorted(p.name for p in SQL_DIR.glob("[0-9][0-9]*.sql") if int(p.name[:2]) >= 4):
        _run_sql(con, name, marts_dir=MARTS.as_posix(), ref_dir=REF.as_posix())


LAYERS = {"stage": stage, "model": model, "marts": marts}


def main(argv: list[str] | None = None) -> int:
    wanted = (argv if argv is not None else sys.argv[1:]) or list(LAYERS)
    unknown = [w for w in wanted if w not in LAYERS]
    if unknown:
        print(f"unknown layer(s): {', '.join(unknown)}; choose from {', '.join(LAYERS)}", file=sys.stderr)
        return 2
    con = connect()
    for layer in wanted:
        LAYERS[layer](con)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
