"""
ActivityLens – Configuration Loader
====================================

What this does:
    Loads config.yaml from the project root, validates it, and provides a
    simple Config object the rest of the code can import.  If the file is
    missing or a key is absent, sensible defaults kick in so the tool works
    out of the box without any setup.

Why a dedicated module instead of just reading YAML inline:
    - Single source of truth for defaults (no magic numbers scattered around)
    - Validation in one place (e.g. polling interval must be > 0)
    - Easy to swap to env-vars or CLI args later without touching every file
"""

import os
import yaml
from pathlib import Path


# ---------------------------------------------------------------------------
# Defaults — used when config.yaml is missing or a key isn't set
# ---------------------------------------------------------------------------
DEFAULTS = {
    "capture": {
        "polling_interval_seconds": 5,
        "idle_threshold_seconds": 300,
    },
    "privacy": {
        "blocklist": {
            "process_names": [],
            "title_patterns": [],
        },
        "retention_days": 30,
    },
    "classification": {
        "productive": {
            "processes": [],
            "browser_titles": [],
        },
        "distracting": {
            "processes": [],
            "browser_titles": [],
        },
    },
    "storage": {
        "db_path": "data/activity.db",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """
    Recursively merge `override` into `base`.
    
    Why not just dict.update()?  Because update() is shallow — it would
    replace the entire "privacy" sub-dict if you only set one key inside it.
    Deep merge lets you override just privacy.retention_days without losing
    the blocklist defaults.
    """
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class Config:
    """
    Thin wrapper around the merged config dict.
    
    Provides dot-style access for readability:
        config.polling_interval   instead of   config["capture"]["polling_interval_seconds"]
    """

    def __init__(self, config_path: str | None = None):
        # Resolve path relative to project root (one level up from src/)
        if config_path is None:
            project_root = Path(__file__).resolve().parent.parent
            config_path = project_root / "config.yaml"
        else:
            config_path = Path(config_path)

        # Load YAML if it exists, otherwise use pure defaults
        raw = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}

        self._data = _deep_merge(DEFAULTS, raw)
        self._validate()

    # --- Convenient accessors -------------------------------------------

    @property
    def polling_interval(self) -> int:
        return self._data["capture"]["polling_interval_seconds"]

    @property
    def idle_threshold(self) -> int:
        return self._data["capture"]["idle_threshold_seconds"]

    @property
    def blocklist_processes(self) -> list[str]:
        """Process names to block, all lowered for case-insensitive matching."""
        return [
            p.lower()
            for p in self._data["privacy"]["blocklist"]["process_names"]
        ]

    @property
    def blocklist_title_patterns(self) -> list[str]:
        """Glob patterns to match against window titles."""
        return [
            p.lower()
            for p in self._data["privacy"]["blocklist"]["title_patterns"]
        ]

    @property
    def retention_days(self) -> int:
        return self._data["privacy"]["retention_days"]

    @property
    def classification_rules(self) -> dict:
        """
        Return classification rules as a dict the classifier module expects.
        
        Structure:
            {
                "productive": {"processes": [...], "browser_titles": [...]},
                "distracting": {"processes": [...], "browser_titles": [...]},
            }
        All patterns are lowercased for case-insensitive matching.
        """
        raw = self._data["classification"]
        return {
            "productive": {
                "processes": [p.lower() for p in raw["productive"]["processes"]],
                "browser_titles": [p.lower() for p in raw["productive"]["browser_titles"]],
            },
            "distracting": {
                "processes": [p.lower() for p in raw["distracting"]["processes"]],
                "browser_titles": [p.lower() for p in raw["distracting"]["browser_titles"]],
            },
        }

    @property
    def db_path(self) -> Path:
        """Resolve db_path relative to the project root."""
        project_root = Path(__file__).resolve().parent.parent
        return project_root / self._data["storage"]["db_path"]

    # --- Validation -----------------------------------------------------

    def _validate(self):
        if self.polling_interval <= 0:
            raise ValueError(
                f"polling_interval_seconds must be > 0, got {self.polling_interval}"
            )
        if self.retention_days <= 0:
            raise ValueError(
                f"retention_days must be > 0, got {self.retention_days}"
            )

    def __repr__(self):
        return (
            f"Config(poll={self.polling_interval}s, "
            f"idle={self.idle_threshold}s, "
            f"retention={self.retention_days}d, "
            f"db={self.db_path})"
        )
