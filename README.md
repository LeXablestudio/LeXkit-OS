# LeXKit — Research OS for Your Files

> CLI-first · Offline-first · Deterministic core · Optional AI · Full reproducibility

[![Version](https://img.shields.io/badge/version-2.0.0-6D28D9)](#)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-6D28D9)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-6D28D9.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-260%20passing-brightgreen)](#)

**Powered by [LeXable Studio](https://lexable-studio-860.created.app/)** — *We don't just process text — we reconstruct knowledge.*

LeXKit is the **offline-first, CLI-first** component of the
[LeXable ecosystem](https://lexable-studio-860.created.app/products). It ships
**9 deterministic CLI tools** (plus a PySide6 desktop GUI) that manage, clean,
search, analyze, and relate your entire academic file library — with a
**deterministic NLP core** (TF-IDF, MinHash, citation parsing) and an
**optional LLM layer** that enriches results when configured, but never breaks
offline use.

LeXKit is designed to work standalone *and* alongside the other LeXable
solutions — [AtlaX](https://lexable-studio-860.created.app/products) (knowledge
graphs), [ArguLeXable](https://lexable-studio-860.created.app/products)
(argument tracking),
[TransLexable](https://lexable-studio-860.created.app/products) (academic
translation), and
[LeXi Agent](https://lexable-studio-860.created.app/products) (ecosystem
orchestration).

---

## What's new in 2.0.0 ("Relate")

LeXKit 2.0 evolves from 8 isolated tools into a **relationally-aware research OS**:

| New | Description |
|-----|-------------|
| **Citation Graph** (`cite`) | Cross-match extracted references against your library to build a who-cites-whom network. Export to **GraphML** (Gephi/NetworkX), **JSON**, or **Graphviz DOT**. |
| **Deterministic NLP core** | TF-IDF vectors, cosine similarity, keyterm extraction, MinHash + LSH near-duplicate clustering — zero ML, zero dependencies. |
| **Similarity search** | `lexkit search similar` finds documents related to an anchor via TF-IDF cosine ranking. |
| **Near-duplicate clustering** | `fsm` and `notes` now detect *near*-duplicates (not just exact SHA-256 matches) via MinHash. |
| **Multi-format citation parsing** | `refs` now parses **APA, MLA, Chicago, Harvard, and numeric/bracket** styles (was APA-only). |
| **Incremental indexing** | `search` tracks file mtime + content hash — re-indexing skips unchanged files. |
| **Optional LLM enrichment** | Configure an OpenAI-compatible backend for higher-quality parsing. **Off by default** — LeXKit stays fully offline & reproducible. |
| **Desktop GUI** | PySide6 dashboard with dark theme, sidebar navigation, 9 tool panels, live streaming output, interactive citation graph, and database-backed result viewers. |

---

## Installation

```bash
pip install lexkit
lexkit --version
# LeXKit v2.0.0 — Research OS
```

Desktop GUI (optional):

```bash
pip install "lexkit[gui]"
lexkit gui
```

From source (for development):

```bash
git clone <repo> && cd lexkit
pip install -e ".[dev]"
pytest -q          # 260 tests
```

---

## Quick Start

```bash
lexkit init ~/research

# 1. Organize your library
lexkit fsm --scan ~/Downloads --auto-sort --cluster    # sort + near-dup clustering

# 2. Clean and extract text
lexkit clean --input ~/research/papers --recursive
lexkit batch extract --input ~/research/papers --output ~/research/text

# 3. Search
lexkit search index --index ~/research/papers
lexkit search query --query "textual criticism methods"
lexkit search similar --dir ~/research/papers --to ~/research/papers/smith2020.pdf

# 4. Citations → Bibliography
lexkit refs extract --input ~/research/papers
lexkit refs export --export bibtex --out bibliography.bib

# 5. Build a citation graph
lexkit cite build --input ~/research/papers
lexkit cite graph --export graphml --out citation.graphml   # open in Gephi
lexkit cite stats

# 6. Generate a paper template
lexkit tpl generate --format mla --title "My Research Paper" --out paper.tex
```

Or run the full pipeline in one command:

```bash
lexkit pipeline --run full --input ~/Downloads/papers
```

---

## The 9 Tools

| Command | Tool | What it does |
|---------|------|--------------|
| `lexkit fsm` | File System Manager | Scan, sort, dedup, near-dup cluster |
| `lexkit clean` | Document Cleaner | Fix PDFs, normalize encoding |
| `lexkit batch` | Batch Processor | Rename, convert, extract text |
| `lexkit search` | Search Engine | Full-text, regex, fuzzy, similarity |
| `lexkit refs` | Reference Manager | Multi-format extract & export |
| `lexkit cite` | Citation Graph | Who-cites-whom network + export |
| `lexkit split` | Lecture Splitter | Split PDFs by table of contents |
| `lexkit notes` | Notes Compiler | Merge & near-dup deduplicate |
| `lexkit tpl` | Template Generator | APA/IEEE/ACM/MLA/Markdown stubs |

---

## Desktop GUI

LeXKit includes an optional PySide6 desktop application — same deterministic
tools, visual interface:

```bash
pip install "lexkit[gui]"
lexkit gui
```

- Dark theme with magenta brand identity
- Sidebar navigation across all 9 tools + 4 result viewers
- Background execution via QThread — UI never blocks
- Live streaming output with ANSI-coloured log panel
- Interactive citation graph with deterministic Fruchterman-Reingold layout
- Database-backed references table, near-duplicate clusters, and statistics

---

## The Deterministic Analysis Core

Every analysis feature runs on a pure-Python, dependency-free NLP engine
(`lexkit/analysis/`) that guarantees reproducibility — the same input always
produces the same output, on any machine, forever.

```python
from lexkit.analysis import TfidfModel, cosine_similarity, MinHasher, shingles, cluster_signatures

# TF-IDF similarity
model = TfidfModel(["neural networks", "graph theory", "medieval studies"])
sim = cosine_similarity(model.transform("neural networks"), model.transform("graph neural"))

# Near-duplicate clustering
mh = MinHasher(num_perm=128)
sigs = {"a": mh.signature(shingles(doc_a)), "b": mh.signature(shingles(doc_b))}
result = cluster_signatures(sigs)  # near-dups grouped together
```

**No models to download. No network calls. No randomness.** Fully deterministic.

---

## Optional AI Enrichment

LeXKit is deterministic by default. To enable optional LLM enrichment for
higher-quality citation parsing, set two environment variables:

```bash
export LEXKIT_LLM_BASE_URL="https://api.openai.com/v1"
export LEXKIT_LLM_API_KEY="sk-..."
export LEXKIT_LLM_MODEL="gpt-4o-mini"   # optional

lexkit refs extract --input ~/research/papers --llm
```

When unconfigured, LeXKit uses `NullLLM` and every tool silently falls back to
the deterministic engine. **No new dependencies are added** — the HTTP client
uses Python's standard `urllib`.

---

## The LeXable Ecosystem

LeXKit is one part of the [LeXable Studio](https://lexable-studio-860.created.app/)
research intelligence infrastructure:

| Solution | Role |
|----------|------|
| [**AtlaX**](https://lexable-studio-860.created.app/products) | Knowledge graphs from books and academic texts |
| [**ArguLeXable**](https://lexable-studio-860.created.app/products) | Argument chain tracking and strength analysis |
| [**TransLexable**](https://lexable-studio-860.created.app/products) | Academic translation across 50+ languages |
| [**LeXi Agent**](https://lexable-studio-860.created.app/products) | Ecosystem orchestrator — cross-solution insight synthesis |
| **LeXKit** (this repo) | Offline CLI toolkit for file management and deterministic NLP |
| [**LeXLabs**](https://lexable-studio-860.created.app/labs) | Custom research infrastructure for institutions |

---

## Architecture

```
lexkit/
├── analysis/          # Deterministic NLP core (tokenizer, TF-IDF, MinHash)
│   ├── tokenizer.py   #   Unicode tokenization, n-grams, stopwords
│   ├── vectors.py     #   TF-IDF model, cosine similarity, keyterms
│   └── minhash.py     #   MinHash signatures, LSH, clustering
├── llm/               # Optional LLM layer (off by default)
│   ├── base.py        #   LLMBackend ABC, NullLLM, JSON parser
│   ├── registry.py    #   get_llm() → NullLLM unless configured
│   └── openai_compat.py # OpenAI-compatible client (stdlib urllib)
├── tools/             # 9 CLI tools
│   ├── cite.py        # Citation graph (build, export, stats)
│   ├── refs.py        # Multi-format citation parser
│   ├── search.py      # Incremental index + similarity search
│   ├── fsm.py         # Near-dup clustering
│   └── ...
├── gui/               # PySide6 desktop GUI
│   ├── app.py         #   MainWindow + entry point
│   ├── theme.py       #   Dark theme QSS stylesheet
│   ├── workers.py     #   QThread-based tool execution
│   └── widgets/       #   Dashboard, tool panels, graph view, tables
├── db/store.py        # SQLite (migration-safe schema)
├── plugins/           # Plugin system (TyperPlugin adapter)
├── cli/main.py        # Root Typer app
└── errors.py          # Error taxonomy
```

---

## Pipelines

```bash
lexkit pipeline --run intake --input ~/Downloads/papers
lexkit pipeline --run export --input ~/research/papers
lexkit pipeline --run full --input ~/Downloads/papers
```

---

## Database

```bash
lexkit db --stats         # files, refs, citation edges, near-dup clusters
lexkit db --list-files    # indexed files
lexkit db --clear         # wipe all records
```

Stored at `~/.lexkit/lexkit.db` (SQLite, WAL mode). The schema auto-migrates
from v1 databases on first open.

---

## Configuration

Settings live at `~/.lexkit/config.json`:

```json
{
  "workspace": "~/research",
  "similarity_threshold": 0.25,
  "near_duplicate_threshold": 0.5,
  "minhash_permutations": 128,
  "llm_backend": "",
  "llm_model": ""
}
```

---

## Plugin Development

```python
import typer
from lexkit.plugins import PluginBase

app = typer.Typer()

class OcrPlugin(PluginBase):
    name = "ocr"
    version = "0.1.0"
    description = "OCR for scanned PDFs"

    @property
    def typer_app(self):
        return app

plugin = OcrPlugin()
```

Register in `pyproject.toml`:

```toml
[project.entry-points."lexkit.plugins"]
ocr = "lexkit_plugin_ocr:plugin"
```

---

## Philosophy

> *We don't just process text — we reconstruct knowledge.*
> — LeXable Studio Research Manifesto

- **Deterministic by default** — same input, same output, always.
- **Offline-first** — no cloud, no models, no tracking.
- **Privacy-first** — all processing stays on your machine.
- **Optional AI** — enrichment available, never required.
- **Full reproducibility** — sorted vocabularies, seeded hashes, UTC timestamps.
- **MIT licensed** — fork and extend freely.

---

## Links

- **Website**: [lexable-studio-860.created.app](https://lexable-studio-860.created.app/)
- **LeXKit page**: [lexable-studio-860.created.app/lexkit](https://lexable-studio-860.created.app/lexkit)
- **Products**: [lexable-studio-860.created.app/products](https://lexable-studio-860.created.app/products)
- **Enterprise**: [lexable-studio-860.created.app/labs](https://lexable-studio-860.created.app/labs)
- **Contact**: [lexable-studio-860.created.app/contact](https://lexable-studio-860.created.app/contact)

---

## License

MIT (c) 2026 LeXable Studio — *Deep Tech. Intelligent Impact.*
