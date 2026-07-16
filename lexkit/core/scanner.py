"""
High-performance directory scanner with multiprocessing support.
Handles 1000+ files efficiently.
"""

from __future__ import annotations

import hashlib
import mimetypes
import multiprocessing as mp
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".tex", ".docx", ".rtf", ".epub"}
YEAR_PATTERN   = re.compile(r"(19|20)\d{2}")
AUTHOR_PATTERN = re.compile(r"^([A-Z][a-z]+(?:[-\s][A-Z][a-z]+)?)")


@dataclass
class FileMetadata:
    path: Path
    name: str
    stem: str
    suffix: str
    size_bytes: int
    size_kb: float
    year: str | None = None
    author: str | None = None
    sha256: str | None = None
    mime_type: str | None = None
    is_duplicate: bool = False
    duplicate_of: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "path": str(self.path), "name": self.name, "stem": self.stem,
            "suffix": self.suffix, "size_bytes": self.size_bytes,
            "size_kb": round(self.size_kb, 2), "year": self.year,
            "author": self.author, "sha256": self.sha256,
            "mime_type": self.mime_type, "is_duplicate": self.is_duplicate,
            "duplicate_of": self.duplicate_of,
        }


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_metadata(path: Path, compute_hash: bool = True) -> FileMetadata:
    stat = path.stat()
    stem = path.stem
    year_m  = YEAR_PATTERN.search(stem)
    author_m = AUTHOR_PATTERN.match(stem.replace("_", " ").replace("-", " "))
    mime, _ = mimetypes.guess_type(str(path))
    return FileMetadata(
        path=path, name=path.name, stem=stem,
        suffix=path.suffix.lower(),
        size_bytes=stat.st_size,
        size_kb=stat.st_size / 1024,
        year=year_m.group() if year_m else None,
        author=author_m.group(1) if author_m else None,
        sha256=compute_sha256(path) if compute_hash else None,
        mime_type=mime,
    )


def _worker(args: tuple[Path, bool]) -> FileMetadata:
    return extract_metadata(args[0], compute_hash=args[1])


def scan_directory(
    directory: Path,
    recursive: bool = True,
    extensions: set[str] | None = None,
    compute_hashes: bool = True,
    workers: int | None = None,
) -> list[FileMetadata]:
    exts = extensions or SUPPORTED_EXTENSIONS
    pattern = "**/*" if recursive else "*"
    paths = [p for p in directory.glob(pattern) if p.is_file() and p.suffix.lower() in exts]
    if not paths:
        return []

    if len(paths) > 200:
        cpu_count = workers or min(mp.cpu_count(), 8)
        with mp.Pool(cpu_count) as pool:
            results = pool.map(_worker, [(p, compute_hashes) for p in paths])
    else:
        results = [extract_metadata(p, compute_hash=compute_hashes) for p in paths]

    if compute_hashes:
        seen: dict[str, str] = {}
        for meta in results:
            if meta.sha256 and meta.sha256 in seen:
                meta.is_duplicate = True
                meta.duplicate_of = seen[meta.sha256]
            elif meta.sha256:
                seen[meta.sha256] = str(meta.path)
    return results


def iter_directory(directory: Path, recursive: bool = True) -> Iterator[Path]:
    pattern = "**/*" if recursive else "*"
    for p in directory.glob(pattern):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield p
