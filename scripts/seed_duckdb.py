"""Compatibility entry point for the fixture pack's deterministic DuckDB seed."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datasets.fixture.source.seed import seed_database

__all__ = ["seed_database"]


if __name__ == "__main__":
    seed_database()
