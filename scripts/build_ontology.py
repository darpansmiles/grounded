"""Emit real producer lineage to the local Marquez service."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ontology.real_lineage import emit_real_lineage

if __name__ == "__main__":
    print(json.dumps(emit_real_lineage(), indent=2))
