"""Persist each declared PostgreSQL source DSN without printing its value."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from governed.cli.secrets import (
    LOCAL_SOURCE_DSNS,
    SECRET_NAME,
    SECRETS_PATH,
    SOURCE_SECRET_NAMES,
    TPCH_SECRET_NAME,
    ensure_local_source_dsns,
    local_source_dsns,
    write_source_dsn,
    write_source_dsns,
)

__all__ = (
    "LOCAL_SOURCE_DSNS",
    "SECRETS_PATH",
    "SECRET_NAME",
    "SOURCE_SECRET_NAMES",
    "TPCH_SECRET_NAME",
    "ensure_local_source_dsns",
    "local_source_dsns",
    "write_source_dsn",
    "write_source_dsns",
)

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
