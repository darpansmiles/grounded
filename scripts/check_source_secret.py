"""Emit a concise preflight failure when a PostgreSQL pack has no source DSN."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import dlt

from packlib import load_pack


def source_dsn_is_configured(dataset: str) -> bool:
    """Check the active pack's declared DSN key without exposing its value."""
    pack = load_pack(dataset)
    if pack.source.type != "postgres" or pack.source.dsn_env is None:
        return True
    value = os.environ.get(pack.source.dsn_env) or dlt.secrets.get(pack.source.dsn_env)
    return isinstance(value, str) and bool(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    arguments = parser.parse_args()
    pack = load_pack(arguments.dataset)
    if not source_dsn_is_configured(arguments.dataset):
        dsn_env = pack.source.dsn_env or "declared source DSN"
        print(
            f"Missing {dsn_env}. Export it for this shell or run "
            f"`{dsn_env}=... make set-secret` before `make spine`.",
            file=sys.stderr,
        )
        raise SystemExit(2)
