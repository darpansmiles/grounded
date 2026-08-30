"""Copy the documented dataset-pack template into a named pack directory."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEMPLATE = ROOT / "datasets" / "_template"


def main() -> None:
    if len(sys.argv) != 2 or Path(sys.argv[1]).name != sys.argv[1]:
        raise SystemExit("Usage: make new-pack NAME=<single-directory-name>")
    name = sys.argv[1]
    destination = ROOT / "datasets" / name
    if destination.exists():
        raise SystemExit(f"Pack already exists: datasets/{name}")
    shutil.copytree(TEMPLATE, destination)
    for path in destination.rglob("*"):
        if path.is_file():
            path.write_text(
                path.read_text(encoding="utf-8").replace("__PACK_NAME__", name),
                encoding="utf-8",
            )
    print(f"Created datasets/{name}. Read datasets/{name}/source/README.md next.")


if __name__ == "__main__":
    main()
