"""Where every input comes from. One place, so the README and the code cannot drift apart.

NADAC (National Average Drug Acquisition Cost) is published by CMS on data.medicaid.gov (DKAN). Each calendar
year is its own dataset; the ids live in data/ref/nadac_ids.json, read from the portal's public catalog
(https://data.medicaid.gov/api/1/metastore/schemas/dataset/items) on 16 Oct 2026, so none is typed by hand.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
WAREHOUSE = ROOT / "data" / "warehouse" / "pw.duckdb"
MARTS = ROOT / "data" / "marts"
REF = ROOT / "data" / "ref"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

MEDICAID_BASE = "https://data.medicaid.gov/api/1/datastore/query"


@dataclass(frozen=True)
class Source:
    key: str
    title: str
    url: str  # file download URL
    filename: str
    count_url: str | None = None  # DKAN query URL that returns the expected row count


def _dkan(uuid: str) -> tuple[str, str]:
    return (
        f"{MEDICAID_BASE}/{uuid}/0/download?format=csv",
        f"{MEDICAID_BASE}/{uuid}/0?limit=1&count=true&schema=false&keys=true",
    )


def nadac_ids() -> dict:
    return json.loads((REF / "nadac_ids.json").read_text(encoding="utf-8"))


def all_sources() -> list[Source]:
    ids = nadac_ids()
    out: list[Source] = []
    for year, uuid in ids["yearly"].items():
        url, count = _dkan(uuid)
        out.append(Source(f"nadac_{year}", f"NADAC weekly rates {year}", url, f"nadac_{year}.csv", count))
    url, count = _dkan(ids["comparison"])
    out.append(Source("nadac_comparison", "NADAC Comparison (current rate against the previous one)", url,
                      "nadac_comparison.csv", count))
    return out
