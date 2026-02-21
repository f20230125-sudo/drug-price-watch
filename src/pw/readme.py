"""Render README.md from docs/README.template.md and dashboard/public/data/headline.json.

    python -m pw.readme            # rewrite README.md
    python -m pw.readme --check    # exit 1 if README.md is out of date (tests/test_readme.py does this)

Every number in the README is a {{path.in.headline|format}} placeholder, so the text cannot drift from the data.
Formats: int (1,234), f1 / f2 (decimals), pct0 / pct1 / abs_pct0 (a share as a percentage), usd_m / usd_b ($1.2M / $1.2B),
usd2 ($3.77), up_pct0 (+22% or -53% from an index against 100), date (2026-10-14 as 14 Oct 2026).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date

from .sources import ROOT

TEMPLATE = ROOT / "docs" / "README.template.md"
OUT = ROOT / "README.md"
HEADLINE = ROOT / "dashboard" / "public" / "data" / "headline.json"
PATTERN = re.compile(r"\{\{\s*([\w.]+)\s*\|\s*(\w+)\s*\}\}")


def fmt(value, kind: str) -> str:
    if kind == "int":
        return f"{round(value):,}"
    if kind == "f1":
        return f"{value:.1f}"
    if kind == "f2":
        return f"{value:.2f}"
    if kind == "pct0":
        return f"{100 * value:.0f}%"
    if kind == "abs_pct0":
        return f"{100 * abs(value):.0f}%"
    if kind == "pct1":
        return f"{100 * value:.1f}%"
    if kind == "usd_m":
        return f"${value / 1e6:,.0f}M"
    if kind == "usd_b":
        return f"${value / 1e9:,.1f}B"
    if kind == "usd2":
        return f"${value:,.2f}"
    if kind == "up_pct0":
        d = value - 100
        return f"{'+' if d >= 0 else '-'}{abs(d):.0f}%"
    if kind == "date":
        return date.fromisoformat(value).strftime("%-d %b %Y") if sys.platform != "win32" else \
            date.fromisoformat(value).strftime("%d %b %Y").lstrip("0")
    raise ValueError(f"unknown format {kind}")


def lookup(data: dict, path: str):
    cur = data
    for part in path.split("."):
        cur = cur[part]
    return cur


def render(template: str, data: dict) -> str:
    return PATTERN.sub(lambda m: fmt(lookup(data, m.group(1)), m.group(2)), template)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    text = render(TEMPLATE.read_text(encoding="utf-8"), json.loads(HEADLINE.read_text(encoding="utf-8")))
    if args.check:
        return 0 if OUT.exists() and OUT.read_text(encoding="utf-8") == text else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.name} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
