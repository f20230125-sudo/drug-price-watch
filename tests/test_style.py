"""House rules for text: no em dashes anywhere in the project's own files."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"node_modules", ".next", "data", "test-results", "playwright-report", "__pycache__", ".git", "out"}
SUFFIXES = {".py", ".sql", ".md", ".ts", ".tsx", ".css", ".json", ".yml", ".yaml", ".ps1", ".mjs", ".txt"}
DASH = chr(0x2014)


def test_no_em_dash_in_any_project_file():
    hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix not in SUFFIXES or SKIP & set(p.relative_to(ROOT).parts):
            continue
        if p.name in {"package-lock.json", "DESIGN.md", "STATUS.md"} or p.name == "test_style.py":
            continue
        if DASH in p.read_text(encoding="utf-8", errors="ignore"):
            hits.append(str(p.relative_to(ROOT)))
    assert hits == [], hits
