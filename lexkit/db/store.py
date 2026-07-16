"""SQLite database store — files, references, search pointers, near-duplicates,
citation edges, and keyterms.

v2.0 extends the v1 schema in a **migration-safe** way: all new tables use
``CREATE TABLE IF NOT EXISTS`` and new columns are added with guarded
``ALTER TABLE`` statements, so a v1 database upgrades transparently the first
time it is opened.

Schema overview
---------------
- ``files``            — scanned documents (+ v2: mtime, content_sha)
- ``references``       — extracted citations
- ``search_pointers``  — index locations per file
- ``near_duplicates``  — MinHash signatures + cluster ids (v2)
- ``citation_edges``   — who-cites-whom graph (v2)
- ``keyterms``         — top TF-IDF terms per file (v2)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE, name TEXT NOT NULL, suffix TEXT,
    size_bytes INTEGER, sha256 TEXT, year TEXT, author TEXT,
    indexed_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS "references" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT, year TEXT, title TEXT NOT NULL, doi TEXT,
    url TEXT, source_file TEXT, added_at TEXT DEFAULT (datetime('now')),
    UNIQUE(title, author, year)
);
CREATE TABLE IF NOT EXISTS search_pointers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    index_path TEXT, term_count INTEGER,
    indexed_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_refs_author ON "references"(author);
-- ── v2.0 tables ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS near_duplicates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    name TEXT,
    minhash TEXT,
    cluster_id INTEGER,
    similarity REAL,
    indexed_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_near_dup_cluster ON near_duplicates(cluster_id);
CREATE TABLE IF NOT EXISTS citation_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    target_file TEXT NOT NULL,
    matched_ref TEXT,
    score REAL,
    added_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_file, target_file)
);
CREATE INDEX IF NOT EXISTS idx_cite_source ON citation_edges(source_file);
CREATE INDEX IF NOT EXISTS idx_cite_target ON citation_edges(target_file);
CREATE TABLE IF NOT EXISTS keyterms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    weight REAL NOT NULL,
    UNIQUE(file_id, term)
);
CREATE INDEX IF NOT EXISTS idx_keyterms_file ON keyterms(file_id);
"""

#: Columns added to the ``files`` table in v2.0 (for incremental indexing).
_FILE_COLUMN_MIGRATIONS: list[tuple[str, str]] = [
    ("mtime", "REAL"),
    ("content_sha", "TEXT"),
]


def get_db(db_path: Path) -> sqlite3.Connection:
    """Open (and lazily migrate) the LeXKit database at ``db_path``."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate_files_columns(conn)
    return conn


def _migrate_files_columns(conn: sqlite3.Connection) -> None:
    """Add v2.0 columns to ``files`` if absent. Idempotent and safe."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(files)").fetchall()}
    for col, col_type in _FILE_COLUMN_MIGRATIONS:
        if col not in existing:
            try:
                conn.execute(f"ALTER TABLE files ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                # Already added concurrently — ignore.
                pass
    conn.commit()


def init_db(db_path: Path) -> None:
    db = get_db(db_path)
    db.commit()
    db.close()


# ── files ─────────────────────────────────────────────────────────────────────

def upsert_file(conn: sqlite3.Connection, meta: dict) -> int:
    c = conn.execute(
        "INSERT INTO files (path,name,suffix,size_bytes,sha256,year,author) "
        "VALUES (:path,:name,:suffix,:size_bytes,:sha256,:year,:author) "
        "ON CONFLICT(path) DO UPDATE SET "
        "size_bytes=excluded.size_bytes,indexed_at=datetime('now') "
        "RETURNING id",
        meta,
    )
    # Must consume the RETURNING cursor before committing, or SQLite raises
    # "cannot commit transaction - SQL statements in progress".
    row = c.fetchone()
    c.close()
    conn.commit()
    return row[0] if row else -1


def set_file_signature(conn: sqlite3.Connection, path: str, *, mtime: float, content_sha: str) -> None:
    """Record mtime + content hash for incremental indexing.

    Lets callers skip re-processing when a file is unchanged since last index.
    """
    conn.execute(
        "UPDATE files SET mtime=?, content_sha=? WHERE path=?",
        (mtime, content_sha, path),
    )
    conn.commit()


def get_file_signature(conn: sqlite3.Connection, path: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT mtime, content_sha FROM files WHERE path=?", (path,)
    ).fetchone()
    return dict(row) if row else None


# ── references ────────────────────────────────────────────────────────────────

def upsert_reference(conn: sqlite3.Connection, ref: dict) -> None:
    conn.execute(
        "INSERT INTO \"references\" (author,year,title,doi,source_file,url) "
        "VALUES (:author,:year,:title,:doi,:source_file,:url) "
        "ON CONFLICT(title,author,year) DO NOTHING",
        {
            "author": ref.get("author"),
            "year": ref.get("year"),
            "title": ref.get("title", ""),
            "doi": ref.get("doi"),
            "url": ref.get("url"),
            "source_file": ref.get("source_file"),
        },
    )
    conn.commit()


def list_references(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM \"references\" ORDER BY year DESC LIMIT ?", (limit,)
        ).fetchall()
    ]


# ── near-duplicates (v2) ──────────────────────────────────────────────────────

def upsert_near_duplicate(
    conn: sqlite3.Connection,
    *,
    path: str,
    name: str | None,
    minhash: str,
    cluster_id: int | None,
    similarity: float | None,
) -> None:
    conn.execute(
        "INSERT INTO near_duplicates (path,name,minhash,cluster_id,similarity) "
        "VALUES (:path,:name,:minhash,:cluster_id,:similarity) "
        "ON CONFLICT(path) DO UPDATE SET "
        "name=excluded.name,minhash=excluded.minhash,"
        "cluster_id=excluded.cluster_id,similarity=excluded.similarity,"
        "indexed_at=datetime('now')",
        {
            "path": path,
            "name": name,
            "minhash": minhash,
            "cluster_id": cluster_id,
            "similarity": similarity,
        },
    )
    conn.commit()


def get_cluster(conn: sqlite3.Connection, cluster_id: int) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT path, name, similarity FROM near_duplicates "
            "WHERE cluster_id=? ORDER BY path",
            (cluster_id,),
        ).fetchall()
    ]


def list_near_duplicates(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT path, name, cluster_id, similarity FROM near_duplicates "
            "ORDER BY cluster_id, path"
        ).fetchall()
    ]


# ── citation edges (v2) ───────────────────────────────────────────────────────

def upsert_citation_edge(
    conn: sqlite3.Connection,
    *,
    source_file: str,
    target_file: str,
    matched_ref: str | None = None,
    score: float = 0.0,
) -> None:
    conn.execute(
        "INSERT INTO citation_edges (source_file,target_file,matched_ref,score) "
        "VALUES (:source_file,:target_file,:matched_ref,:score) "
        "ON CONFLICT(source_file,target_file) DO UPDATE SET "
        "matched_ref=excluded.matched_ref,score=excluded.score",
        {
            "source_file": source_file,
            "target_file": target_file,
            "matched_ref": matched_ref,
            "score": score,
        },
    )
    conn.commit()


def list_citation_edges(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT source_file, target_file, matched_ref, score "
            "FROM citation_edges ORDER BY source_file, target_file"
        ).fetchall()
    ]


def clear_citation_edges(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM citation_edges")
    conn.commit()


# ── keyterms (v2) ─────────────────────────────────────────────────────────────

def upsert_keyterms(conn: sqlite3.Connection, file_id: int, terms: list[tuple[str, float]]) -> None:
    """Replace a file's stored keyterms with the supplied ``[(term, weight), …]``."""
    conn.execute("DELETE FROM keyterms WHERE file_id=?", (file_id,))
    conn.executemany(
        "INSERT OR REPLACE INTO keyterms (file_id,term,weight) VALUES (?,?,?)",
        [(file_id, t, w) for t, w in terms],
    )
    conn.commit()


def list_keyterms(conn: sqlite3.Connection, file_id: int, limit: int = 20) -> list[tuple[str, float]]:
    return [
        (r["term"], r["weight"])
        for r in conn.execute(
            "SELECT term, weight FROM keyterms WHERE file_id=? "
            "ORDER BY weight DESC, term ASC LIMIT ?",
            (file_id, limit),
        ).fetchall()
    ]


# ── listing & stats ───────────────────────────────────────────────────────────

def list_all_files(db_path: Path) -> list[dict]:
    conn = get_db(db_path)
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT path, name, size_bytes/1024 as size_kb FROM files ORDER BY name"
        ).fetchall()
    ]
    conn.close()
    return rows


def get_stats(db_path: Path) -> dict[str, Any]:
    conn = get_db(db_path)
    files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    refs = conn.execute("SELECT COUNT(*) FROM \"references\"").fetchone()[0]
    terms = conn.execute("SELECT COALESCE(SUM(term_count),0) FROM search_pointers").fetchone()[0]
    edges = conn.execute("SELECT COUNT(*) FROM citation_edges").fetchone()[0]
    clusters = conn.execute(
        "SELECT COUNT(DISTINCT cluster_id) FROM near_duplicates WHERE cluster_id IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    size = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0
    return {
        "files": files,
        "refs": refs,
        "terms": terms,
        "citation_edges": edges,
        "near_dup_clusters": clusters,
        "size_mb": size,
    }


def clear_db(db_path: Path) -> None:
    conn = get_db(db_path)
    conn.executescript(
        "DELETE FROM search_pointers; "
        "DELETE FROM \"references\"; "
        "DELETE FROM files; "
        "DELETE FROM near_duplicates; "
        "DELETE FROM citation_edges; "
        "DELETE FROM keyterms;"
    )
    conn.commit()
    conn.close()
