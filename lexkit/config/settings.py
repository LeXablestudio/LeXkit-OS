"""LeXKit settings stored at ~/.lexkit/config.json

v2.0 adds optional AI + similarity configuration. All new fields default to
deterministic/offline values, so upgrading a v1 config changes nothing about
LeXKit's behaviour until the user explicitly opts in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

HOME = Path.home() / ".lexkit"


@dataclass
class Settings:
    """User configuration. Persisted to :attr:`config_path` as JSON."""

    workspace: Path = field(default_factory=lambda: Path.home() / "research")
    lexkit_home: Path = field(default_factory=lambda: HOME)
    db_name: str = "lexkit.db"
    max_workers: int = 8

    # ── v2.0: similarity & near-duplicate tuning (deterministic) ──────────────
    #: Minimum cosine similarity (0–1) for two docs to count as "similar".
    similarity_threshold: float = 0.25
    #: Minimum MinHash signature similarity (0–1) for near-duplicate clustering.
    near_duplicate_threshold: float = 0.5
    #: Number of MinHash permutations for near-duplicate detection.
    minhash_permutations: int = 128

    # ── v2.0: optional AI enrichment (off by default) ─────────────────────────
    #: ``""`` = no backend (NullLLM, fully offline). ``"openai-compat"`` to enable.
    llm_backend: str = ""
    #: Model name passed to the backend (e.g. ``"gpt-4o-mini"``).
    llm_model: str = ""

    @property
    def db_path(self) -> Path:
        return self.lexkit_home / self.db_name

    @property
    def config_path(self) -> Path:
        return self.lexkit_home / "config.json"

    def to_dict(self) -> dict:
        return {
            "workspace": str(self.workspace),
            "lexkit_home": str(self.lexkit_home),
            "db_name": self.db_name,
            "max_workers": self.max_workers,
            "similarity_threshold": self.similarity_threshold,
            "near_duplicate_threshold": self.near_duplicate_threshold,
            "minhash_permutations": self.minhash_permutations,
            "llm_backend": self.llm_backend,
            "llm_model": self.llm_model,
        }

    def save(self) -> None:
        self.lexkit_home.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load_default(cls) -> "Settings":
        # Allow LEXKIT_HOME env var to override the default home — useful for
        # portable installs, testing, and pointing the GUI at a specific DB.
        import os
        env_home = os.environ.get("LEXKIT_HOME")
        home = Path(env_home) if env_home else HOME
        cfg = home / "config.json"
        if cfg.exists():
            try:
                d = json.loads(cfg.read_text())
                return cls(
                    workspace=Path(d.get("workspace", str(Path.home() / "research"))),
                    lexkit_home=Path(d.get("lexkit_home", str(home))),
                    db_name=d.get("db_name", "lexkit.db"),
                    max_workers=d.get("max_workers", 8),
                    similarity_threshold=d.get("similarity_threshold", 0.25),
                    near_duplicate_threshold=d.get("near_duplicate_threshold", 0.5),
                    minhash_permutations=d.get("minhash_permutations", 128),
                    llm_backend=d.get("llm_backend", ""),
                    llm_model=d.get("llm_model", ""),
                )
            except Exception:
                pass
        return cls()
