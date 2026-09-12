from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.stac_pipeline import run

if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
