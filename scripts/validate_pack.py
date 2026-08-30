"""Validate a pack manifest with actionable setup errors."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packlib import load_pack


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: make validate-pack DATASET=<pack-name>")
    name = sys.argv[1]
    try:
        pack = load_pack(name)
    except (FileNotFoundError, TypeError, ValueError) as exc:
        raise SystemExit(f"Invalid pack {name!r}: {exc}") from exc
    if pack.source.dsn_env and not os.environ.get(pack.source.dsn_env):
        raise SystemExit(
            f"Pack {name!r} requires {pack.source.dsn_env}. Set it before make spine."
        )
    print(
        f"Pack {name!r} is valid: source={pack.source.type}, "
        f"backend={pack.semantics.backend if pack.semantics else 'none'}, "
        f"golden={pack.golden.relative_to(pack.root)}"
    )


if __name__ == "__main__":
    main()
