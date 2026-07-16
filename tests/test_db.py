"""Tests for SQLite store — v2.0 extensions (near-dups, citation edges, keyterms, migration)."""

import sqlite3
from pathlib import Path

import pytest

from lexkit.db.store import (
    get_db,
    init_db,
    upsert_file,
    upsert_reference,
    list_references,
    get_stats,
    clear_db,
    set_file_signature,
    get_file_signature,
    upsert_near_duplicate,
    get_cluster,
    list_near_duplicates,
    upsert_citation_edge,
    list_citation_edges,
    clear_citation_edges,
    upsert_keyterms,
    list_keyterms,
)


class TestDatabase:
    def test_creates_tables(self, tmp_path):
        db_path = tmp_path / "t.db"
        init_db(db_path)
        conn = get_db(db_path)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        for t in ("files", "references", "search_pointers", "near_duplicates", "citation_edges", "keyterms"):
            assert t in names, f"table {t} missing"

    def test_upsert_file(self, tmp_path):
        conn = get_db(tmp_path / "t.db")
        fid = upsert_file(conn, {
            "path": "/f.txt", "name": "f.txt", "suffix": ".txt",
            "size_bytes": 10, "sha256": "abc", "year": "2024", "author": "S",
        })
        assert fid > 0
        conn.close()

    def test_no_duplicate_refs(self, tmp_path):
        conn = get_db(tmp_path / "t.db")
        ref = {"author": "S", "year": "2023", "title": "T", "doi": None, "source_file": None}
        upsert_reference(conn, ref)
        upsert_reference(conn, ref)
        assert len(list_references(conn)) == 1
        conn.close()

    def test_stats(self, tmp_path):
        db_path = tmp_path / "t.db"
        init_db(db_path)
        s = get_stats(db_path)
        assert s["files"] == 0 and s["refs"] == 0


class TestV2Schema:
    def test_files_mtime_columns(self, tmp_path):
        conn = get_db(tmp_path / "t.db")
        cols = {r[1] for r in conn.execute("PRAGMA table_info(files)").fetchall()}
        assert "mtime" in cols
        assert "content_sha" in cols
        conn.close()

    def test_file_signature_roundtrip(self, tmp_path):
        conn = get_db(tmp_path / "t.db")
        upsert_file(conn, {"path": "/a.pdf", "name": "a.pdf", "suffix": ".pdf",
                           "size_bytes": 10, "sha256": "x", "year": "2020", "author": "A"})
        set_file_signature(conn, "/a.pdf", mtime=1.5, content_sha="sha1")
        sig = get_file_signature(conn, "/a.pdf")
        assert sig == {"mtime": 1.5, "content_sha": "sha1"}
        conn.close()

    def test_near_duplicates(self, tmp_path):
        conn = get_db(tmp_path / "t.db")
        upsert_near_duplicate(conn, path="/a.pdf", name="a.pdf", minhash="[]", cluster_id=0, similarity=0.9)
        upsert_near_duplicate(conn, path="/b.pdf", name="b.pdf", minhash="[]", cluster_id=0, similarity=0.85)
        cluster = get_cluster(conn, 0)
        assert len(cluster) == 2
        all_dups = list_near_duplicates(conn)
        assert len(all_dups) == 2
        conn.close()

    def test_citation_edges(self, tmp_path):
        conn = get_db(tmp_path / "t.db")
        upsert_citation_edge(conn, source_file="/a.pdf", target_file="/b.pdf", score=0.8)
        upsert_citation_edge(conn, source_file="/a.pdf", target_file="/b.pdf", score=0.9)  # upsert
        assert len(list_citation_edges(conn)) == 1
        clear_citation_edges(conn)
        assert list_citation_edges(conn) == []
        conn.close()

    def test_keyterms(self, tmp_path):
        conn = get_db(tmp_path / "t.db")
        fid = upsert_file(conn, {"path": "/f.txt", "name": "f.txt", "suffix": ".txt",
                                  "size_bytes": 10, "sha256": "x", "year": "2024", "author": "S"})
        upsert_keyterms(conn, fid, [("neural", 0.5), ("graphs", 0.3)])
        kt = list_keyterms(conn, fid)
        assert kt == [("neural", 0.5), ("graphs", 0.3)]
        conn.close()

    def test_stats_v2_fields(self, tmp_path):
        conn = get_db(tmp_path / "t.db")
        upsert_file(conn, {"path": "/f.txt", "name": "f.txt", "suffix": ".txt",
                           "size_bytes": 10, "sha256": "x", "year": "2024", "author": "S"})
        upsert_citation_edge(conn, source_file="/f.txt", target_file="/g.pdf", score=0.7)
        conn.close()
        s = get_stats(tmp_path / "t.db")
        assert s["citation_edges"] == 1


class TestV1Migration:
    def test_v1_db_upgrades(self, tmp_path):
        """Simulate a v1 DB (no mtime/content_sha columns, no v2 tables) and reopen."""
        db_path = tmp_path / "v1.db"
        c = sqlite3.connect(str(db_path))
        c.executescript("""
            CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT UNIQUE, name TEXT, suffix TEXT,
              size_bytes INTEGER, sha256 TEXT, year TEXT, author TEXT, indexed_at TEXT);
            CREATE TABLE "references" (id INTEGER PRIMARY KEY, author TEXT, year TEXT, title TEXT, doi TEXT,
              url TEXT, source_file TEXT, added_at TEXT, UNIQUE(title,author,year));
            CREATE TABLE search_pointers (id INTEGER PRIMARY KEY, file_id INTEGER, index_path TEXT,
              term_count INTEGER, indexed_at TEXT);
            INSERT INTO "references" (author, year, title) VALUES ('Old', '2019', 'Legacy Ref');
        """)
        c.commit()
        c.close()

        # Reopen via get_db — should add columns + new tables without error.
        conn = get_db(db_path)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(files)").fetchall()}
        assert "mtime" in cols
        assert "content_sha" in cols
        # Existing data preserved.
        assert len(list_references(conn)) == 1
        # New tables exist.
        tbls = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "near_duplicates" in tbls
        assert "citation_edges" in tbls
        assert "keyterms" in tbls
        conn.close()

    def test_idempotent_reopen(self, tmp_path):
        """Opening the same DB twice doesn't fail."""
        conn = get_db(tmp_path / "t.db")
        conn.close()
        conn = get_db(tmp_path / "t.db")
        conn.close()
