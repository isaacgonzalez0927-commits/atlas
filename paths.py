"""Atlas data paths."""

from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).parent
DATA_ROOT = Path(os.getenv("ATLAS_DATA_DIR", str(HERE / "data")))
DATA_ROOT.mkdir(parents=True, exist_ok=True)
SNAPSHOT_FILE = DATA_ROOT / "atlas_snapshot.json"
