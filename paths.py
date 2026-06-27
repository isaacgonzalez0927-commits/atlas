"""Atlas data paths — single data root for clients, leads, and backups."""

from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).parent


def _resolve_data_root() -> Path:
    explicit = os.getenv("ATLAS_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit)
    # Render web services should use the mounted disk at /data when env is unset.
    if os.getenv("RENDER") == "true":
        return Path("/data")
    return HERE / "data"


DATA_ROOT = _resolve_data_root()
DATA_ROOT.mkdir(parents=True, exist_ok=True)

SNAPSHOT_FILE = DATA_ROOT / "atlas_snapshot.json"
HISTORY_FILE = DATA_ROOT / "generated_history.json"
JOBS_DIR = DATA_ROOT / "jobs"
LEARN_CACHE_FILE = DATA_ROOT / "learn_cache.json"

JOBS_DIR.mkdir(parents=True, exist_ok=True)
