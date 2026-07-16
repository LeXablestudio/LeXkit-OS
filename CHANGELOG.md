# Changelog

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [2.0.0] — 2026-06-26 — "Relate"

The "Relate" release evolves LeXKit from 8 isolated tools into a
**relationally-aware research OS** — a deterministic NLP core, deepened tools, a
new citation-graph tool, and an optional LLM layer. Philosophy preserved:
deterministic by default, offline-first, fully reproducible.

### Added — New tools & subsystems

- **Citation Graph tool** (`lexkit cite`) — cross-match extracted references
  against the library to build a who-cites-whom network via TF-IDF title
  similarity + filename heuristics. Export to GraphML (Gephi/NetworkX), JSON, or
  Graphviz DOT. Subcommands: `build`, `graph`, `stats`, `list`.
- **Deterministic NLP core** (`lexkit/analysis/`) — zero-dependency engine:
  - `tokenizer.py` — Unicode tokenization, n-grams, sentence splitting,
    curated academic stopwords, light stemmer.
  - `vectors.py` — `TfidfModel` with sorted (reproducible) vocabulary, L2-normalised
    sparse vectors, cosine similarity, `keyterms()`.
  - `minhash.py` — `MinHasher` (seeded `blake2b` permutations), exact Jaccard,
    `LSH` banding, and `cluster_signatures()` with union-find.
- **Optional LLM layer** (`lexkit/llm/`) — `LLMBackend` ABC, `NullLLM` (the
  default, always-off), `OpenAICompatibleLLM` (stdlib `urllib`, no new deps).
  Activated only when `LEXKIT_LLM_BASE_URL` + `LEXKIT_LLM_API_KEY` are set.

### Added — Tool upgrades

- `refs` — **multi-format citation parsing** (APA, MLA, Chicago, Harvard,
  numeric/bracket) with cross-style dedup disambiguation; DOI/URL normalization;
  `--llm` flag for optional enrichment. New renderers: MLA, Chicago.
- `search` — **incremental indexing** (tracks file mtime + content SHA-256,
  skips unchanged files); new `similar` command for TF-IDF cosine ranking;
  extracted-text sidecar caching.
- `fsm` — **near-duplicate clustering** (`--cluster`) via MinHash alongside
  exact SHA-256 dedup; richer auto-classify topic buckets.
- `notes` — **near-duplicate paragraph dedup** via MinHash; `--near-dup-threshold`.
- `tpl` — new **MLA** LaTeX template and a generic **Markdown** research-log template.

### Added — DB & config

- Migration-safe schema extensions: `near_duplicates`, `citation_edges`,
  `keyterms` tables; `mtime`/`content_sha` columns on `files` for incremental
  indexing. New helpers: `upsert_near_duplicate`, `get_cluster`,
  `upsert_citation_edge`, `list_citation_edges`, `set_file_signature`,
  `get_file_signature`, `upsert_keyterms`, `list_keyterms`.
- `Settings` gains `similarity_threshold`, `near_duplicate_threshold`,
  `minhash_permutations`, `llm_backend`, `llm_model` (all default to
  deterministic/offline values).

### Added — Plugin system

- `TyperPlugin` adapter so built-in bare `typer.Typer` apps register cleanly
  with metadata. Loader auto-wraps Typer apps discovered via entry points.

### Fixed

- **`refs.py` SyntaxError** — unterminated f-string in `_chicago` made the
  module unimportable.
- **Broken build backend** — `setuptools.backends.legacy:build` (nonexistent)
  → `setuptools.build_meta`.
- **Plugin loader / entry-point mismatch** — built-in tools now register and
  appear in the CLI reliably.
- **SQLite `references` reserved word** — table name crashed on Python 3.13's
  newer SQLite; now quoted everywhere.
- **`upsert_file` commit-while-cursor-open** — consume `RETURNING` before commit.
- **GraphML namespace** — corrected to the canonical `graphml.graphdrawing.org`.

### Tests

- 162 tests passing. New suites: `test_nlp_tokenizer.py`,
  `test_nlp_vectors.py`, `test_minhash.py`, `test_llm.py`, `test_cite.py`;
  extended `test_refs.py` (multi-format) and `test_db.py` (v2 schema + v1
  migration). Updated `test_plugins.py` for the `TyperPlugin` adapter.

---

## [1.0.0] — 2026-06-12 — Stable Release

### Added
- **Plugin System** — dynamic tool loading via `importlib.metadata` entry points
- **Error Taxonomy** — structured exception hierarchy (`lexkit/errors.py`)
  - `LexKitError` (E000) — base class with `code` and `context` attributes
  - `LexKitScanError` (E001) — file scanning failures
  - `LexKitCleanError` (E002) — document cleaning failures
  - `LexKitSearchError` (E003) — index and query failures
  - `LexKitDatabaseError` (E004) — SQLite operation failures
  - `LexKitPluginError` (E005) — plugin load/register failures
  - `LexKitPipelineError` (E006) — pipeline execution failures
  - `wrap()` context manager — converts stdlib exceptions to typed LexKit errors
- **Structured Logging** — JSON-lines logger (`lexkit/logging.py`)
  - Deterministic ISO-8601 timestamps (UTC, microsecond precision)
  - Fields: `ts`, `level`, `tool`, `event`, `error_code`, `context`
  - Log file at `~/.lexkit/lexkit.log`
  - Zero randomness — all output reproducible given same input
- **Plugin Registry** — `lexkit/plugins/registry.py` with thread-safe registration
- **Plugin Loader** — `lexkit/plugins/loader.py` — discovers plugins from entry points
- `PluginBase` abstract class with `name`, `version`, `app` contract
- `lexkit plugins --list` CLI command — shows all loaded plugins
- `CONTRIBUTING.md` updated with plugin authoring guide
- `Makefile` with `lint`, `test`, `build`, `publish` targets
- `PUBLISHING.md` — step-by-step PyPI release guide

### Changed
- Version: `1.0.0b1` → `1.0.0`
- PyPI classifier: `Development Status :: 4 - Beta` → `5 - Production/Stable`
- All tools now raise typed exceptions (`LexKitError` subclasses) instead of bare `Exception`
- All tools emit structured log events via `lexkit.logging.log()`
- `pyproject.toml` — added `[project.entry-points."lexkit.plugins"]` group
- `pyproject.toml` — added `build` and `twine` to `[dev]` extras
- `lexkit/cli/main.py` — dynamically loads plugins at startup via `PluginLoader`
- `lexkit/core/scanner.py` — uses `LexKitScanError` on failures
- `lexkit/db/store.py` — uses `LexKitDatabaseError` on failures

### Fixed
- Determinism: removed all `datetime.now()` calls from deterministic output paths
- Hash collisions: SHA-256 deduplication now correctly handles empty files
- Pipeline runner: steps no longer silently swallow `LexKitError` subclasses

### Security
- SQLite connections use WAL journal mode and parameterised queries throughout
- No shell injection vectors in batch rename or sort operations

---

## [1.0.0b1] — 2026-06-01 — Beta

### Added
- Initial 8-tool CLI suite: `fsm`, `clean`, `batch`, `search`, `refs`, `split`, `notes`, `tpl`
- SQLite database backend
- Whoosh full-text search engine
- Pipeline system (`intake`, `export`, `full`)
- APA, IEEE, ACM paper templates (LaTeX)
- BibTeX, APA, MLA, Chicago citation export
- Multiprocessing file scanner (handles 1000+ files)
- pytest test suite (6 test modules, 30+ test cases)
