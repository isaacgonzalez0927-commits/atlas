"""Atlas data paths — single data root for clients, leads, and backups."""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _resolve_data_root() -> Path:
    explicit = os.getenv("ATLAS_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit)

    # Prefer Render persistent disk when mounted at /data.
    if os.getenv("RENDER") == "true":
        disk = Path("/data")
        if _is_writable_dir(disk):
            return disk
        print(
            "[atlas] WARNING: /data is not writable — using app data/ folder. "
            "Attach a Render disk at /data for persistence.",
            file=sys.stderr,
            flush=True,
        )

    return HERE / "data"


DATA_ROOT = _resolve_data_root()
if not _is_writable_dir(DATA_ROOT):
    fallback = HERE / "data"
    print(
        f"[atlas] WARNING: cannot use {DATA_ROOT}; falling back to {fallback}",
        file=sys.stderr,
        flush=True,
    )
    DATA_ROOT = fallback
    DATA_ROOT.mkdir(parents=True, exist_ok=True)

SNAPSHOT_FILE = DATA_ROOT / "atlas_snapshot.json"
HISTORY_FILE = DATA_ROOT / "generated_history.json"
JOBS_DIR = DATA_ROOT / "jobs"
LEARN_CACHE_FILE = DATA_ROOT / "learn_cache.json"

JOBS_DIR.mkdir(parents=True, exist_ok=True)
