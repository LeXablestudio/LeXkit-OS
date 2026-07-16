"""File metadata extraction utilities."""
from __future__ import annotations

import re
from pathlib import Path

YEAR_RE   = re.compile(r"(19|20)\d{2}")
AUTHOR_RE = re.compile(r"^([A-Z][a-z]+(?:[-\s][A-Z][a-z]+)?)")

def extract_year(filename: str) -> str | None:
    m = YEAR_RE.search(filename); return m.group() if m else None

def extract_author(filename: str) -> str | None:
    m = AUTHOR_RE.match(filename.replace("_"," ").replace("-"," ")); return m.group(1) if m else None

def extract_pdf_metadata(path: Path) -> dict:
    try:
        import fitz
        doc = fitz.open(str(path)); meta = doc.metadata or {}; doc.close()
        return {"title": meta.get("title",""), "author": meta.get("author",""), "subject": meta.get("subject","")}
    except Exception:
        return {}
