"""Tests for the Citation Graph tool — export formats, edge handling."""

import json
import tempfile
from pathlib import Path

import pytest

from lexkit.db.store import (
    get_db,
    upsert_citation_edge,
    list_citation_edges,
    clear_citation_edges,
)
from lexkit.tools.cite import (
    _write_graphml,
    _write_json,
    _write_dot,
)


@pytest.fixture
def tmpdb(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_db(db_path)
    yield conn
    conn.close()


@pytest.fixture
def sample_edges():
    return [
        {"source_file": "/a.pdf", "target_file": "/b.pdf", "matched_ref": "Smith 2020", "score": 0.8},
        {"source_file": "/a.pdf", "target_file": "/c.pdf", "matched_ref": "Jones 2021", "score": 0.6},
        {"source_file": "/b.pdf", "target_file": "/c.pdf", "matched_ref": "Lee 2019", "score": 0.7},
    ]


class TestCitationEdges:
    def test_upsert_and_list(self, tmpdb, sample_edges):
        for e in sample_edges:
            upsert_citation_edge(tmpdb, **e)
        edges = list_citation_edges(tmpdb)
        assert len(edges) == 3

    def test_upsert_dedup(self, tmpdb):
        upsert_citation_edge(tmpdb, source_file="/a.pdf", target_file="/b.pdf", score=0.5)
        upsert_citation_edge(tmpdb, source_file="/a.pdf", target_file="/b.pdf", score=0.9)
        edges = list_citation_edges(tmpdb)
        assert len(edges) == 1
        assert edges[0]["score"] == 0.9  # updated

    def test_clear(self, tmpdb, sample_edges):
        for e in sample_edges:
            upsert_citation_edge(tmpdb, **e)
        clear_citation_edges(tmpdb)
        assert list_citation_edges(tmpdb) == []


class TestExportFormats:
    def test_graphml(self, sample_edges, tmp_path):
        out = tmp_path / "graph.graphml"
        _write_graphml(sample_edges, out)
        content = out.read_text(encoding="utf-8")
        assert '<?xml version="1.0"' in content
        assert 'graphml' in content
        assert 'source="/a.pdf"' in content or "source=" in content

    def test_json_export(self, sample_edges, tmp_path):
        out = tmp_path / "graph.json"
        _write_json(sample_edges, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["directed"] is True
        assert len(data["edges"]) == 3
        assert data["edges"][0]["source"] == "/a.pdf"

    def test_dot_export(self, sample_edges, tmp_path):
        out = tmp_path / "graph.dot"
        _write_dot(sample_edges, out)
        content = out.read_text(encoding="utf-8")
        assert "digraph" in content
        assert "->" in content
