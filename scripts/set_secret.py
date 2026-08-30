"""Persist each declared PostgreSQL source DSN without printing its value."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SECRET_NAME = "GROUNDED_ADVENTUREWORKS_SOURCE_DSN"
TPCH_SECRET_NAME = "GROUNDED_TPCH_SOURCE_DSN"
SOURCE_SECRET_NAMES = (SECRET_NAME, TPCH_SECRET_NAME)
SECRETS_PATH = Path(".dlt/secrets.toml")


def write_source_dsn(
    value: str, path: Path = SECRETS_PATH, *, name: str = SECRET_NAME
) -> None:
    """Update one source-DSN key while preserving unrelated secret entries."""
    if not value:
        raise ValueError(f"{name} must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{name} = {json.dumps(value)}"
    contents = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(rf"(?m)^{re.escape(name)}\s*=.*$")
    updated = pattern.sub(line, contents) if pattern.search(contents) else contents.rstrip() + f"\n{line}\n"
    path.write_text(updated, encoding="utf-8")


def write_source_dsns(values: dict[str, str], path: Path = SECRETS_PATH) -> None:
    """Persist every declared PostgreSQL source DSN in one local secrets file."""
    for name in SOURCE_SECRET_NAMES:
        write_source_dsn(values.get(name, ""), path, name=name)


if __name__ == "__main__":
    dsns = {name: os.environ.get(name, "") for name in SOURCE_SECRET_NAMES}
    try:
        write_source_dsns(dsns)
    except ValueError as exc:
        print(
            f"{exc}. Export every declared source DSN, then run `make set-secret`; "
            "the values are not printed.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    print(f"Saved {', '.join(SOURCE_SECRET_NAMES)} to {SECRETS_PATH}; this local file persists between runs.")
