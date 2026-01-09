"""Download every raw input into data/raw/.

    python -m pw.fetch                # everything that is missing
    python -m pw.fetch nadac_2024     # one source
    python -m pw.fetch --force        # re-download

Files are written to a .part name and renamed when complete, so an interrupted run never leaves a
half-file that looks finished. The expected row count is read from the API first and saved to
data/raw/expected_rows.json; `pw.build` compares it with what landed in the warehouse.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import requests

from .sources import RAW, USER_AGENT, Source, all_sources

HEADERS = {"User-Agent": USER_AGENT, "Accept": "*/*"}
CHUNK = 1 << 20


def expected_rows(src: Source) -> int | None:
    if not src.count_url:
        return None
    r = requests.get(src.count_url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return int(r.json()["count"])


def download(src: Source, force: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / src.filename
    if dest.exists() and not force:
        print(f"  have  {src.filename} ({dest.stat().st_size / 1e6:,.0f} MB)")
        return
    part = dest.with_suffix(dest.suffix + ".part")
    started = time.time()
    with requests.get(src.url, headers=HEADERS, stream=True, timeout=(30, 120)) as r:
        r.raise_for_status()
        done = 0
        with open(part, "wb") as f:
            for block in r.iter_content(CHUNK):
                f.write(block)
                done += len(block)
    part.replace(dest)
    print(f"  got   {src.filename} ({done / 1e6:,.0f} MB in {time.time() - started:,.0f}s)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keys", nargs="*", help="source keys to fetch (default: all)")
    ap.add_argument("--force", action="store_true", help="download again even if the file exists")
    args = ap.parse_args(argv)

    sources = [s for s in all_sources() if not args.keys or s.key in args.keys]
    if not sources:
        print("no matching source", file=sys.stderr)
        return 2

    counts: dict[str, int] = {}
    for src in sources:
        print(f"{src.key}: {src.title}", flush=True)
        try:
            n = expected_rows(src)
            if n is not None:
                counts[src.key] = n
                print(f"  rows expected {n:,}", flush=True)
            download(src, args.force)
        except requests.RequestException as e:
            print(f"  FAILED {e}", file=sys.stderr)
            return 1
    if counts:
        RAW.mkdir(parents=True, exist_ok=True)
        merged: dict[str, int] = {}
        manifest = RAW / "expected_rows.json"
        if manifest.exists():
            merged = json.loads(manifest.read_text())
        merged.update(counts)
        manifest.write_text(json.dumps(merged, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
