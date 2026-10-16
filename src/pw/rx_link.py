"""Bring the pieces of Rx Market Pulse (the sibling project, rx-analytics) that Drug Price Watch needs.

NADAC says what a pharmacy paid per unit. To turn prices into an index we need how many units moved, and to say
which products are brands we need the product records. Rx Market Pulse already holds both for the US Medicaid
programme, so this module copies a compact extract into data/ref/ (committed, so this repo builds without it):

    rx_ndc_attrs.csv.gz    one row per NDC: brand/generic, product family, ingredient, owner, therapeutic area
    rx_units_year.csv.gz   NDC x year: units, prescriptions, Medicaid spend (2019-2025, before rebates)
    rx_erosion_events.csv  the 48 molecules whose first generic arrived in the data window
    rx_pvm.csv             Rx Market Pulse's price-volume-mix bridge (the price effect is the figure NADAC is compared with)

    python -m pw.rx_link --refresh      # rewrite the extracts from rx-analytics (only if Rx Market Pulse changes)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

from . import sources as S

RX_WAREHOUSE = Path(r"D:\claude-workspace\rx-analytics\data\warehouse\rx.duckdb")

OUT = {
    "attrs": S.REF / "rx_ndc_attrs.csv.gz",
    "units": S.REF / "rx_units_year.csv.gz",
    "events": S.REF / "rx_erosion_events.csv",
    "pvm": S.REF / "rx_pvm.csv",
}


def refresh(src: Path = RX_WAREHOUSE) -> dict[str, int]:
    con = duckdb.connect(str(src), read_only=True)
    counts: dict[str, int] = {}
    jobs = {
        "attrs": """
            select ndc11, any_value(market_class) as market_class, any_value(family) as family,
                   any_value(ingredient) as ingredient, any_value(owner) as owner, any_value(area) as area,
                   bool_or(is_biologic) as is_biologic
            from sales_nat group by ndc11 order by ndc11""",
        "units": """
            select ndc11, year, round(sum(units), 3) as units, round(sum(rx)) as rx, round(sum(spend), 2) as spend
            from sales_nat group by ndc11, year order by ndc11, year""",
        "events": "select * from mart_erosion_events order by entry_quarter, ingredient",
        "pvm": "select * from mart_pvm order by y0, y1, segment",
    }
    for key, sql in jobs.items():
        dest = OUT[key]
        dest.parent.mkdir(parents=True, exist_ok=True)
        con.execute(f"copy ({sql}) to '{dest.as_posix()}' (header, delimiter ',')")
        counts[key] = con.execute(f"select count(*) from ({sql})").fetchone()[0]
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)
    if not args.refresh:
        ap.print_help()
        return 0
    if not RX_WAREHOUSE.exists():
        print(f"missing {RX_WAREHOUSE}", file=sys.stderr)
        return 1
    for k, n in refresh().items():
        print(f"{k}: {n:,} rows -> {OUT[k].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
