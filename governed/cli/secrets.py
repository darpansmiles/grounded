"""Local development source-secret helpers shared by the CLI and Make wrapper."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

SECRET_NAME = "GROUNDED_ADVENTUREWORKS_SOURCE_DSN"
TPCH_SECRET_NAME = "GROUNDED_TPCH_SOURCE_DSN"
SOURCE_SECRET_NAMES = (SECRET_NAME, TPCH_SECRET_NAME)
SECRETS_PATH = Path(".dlt/secrets.toml")
LOCAL_SOURCE_DSNS = {
    SECRET_NAME: "postgresql://grounded:grounded_local_password@localhost:5433/adventureworks",
    TPCH_SECRET_NAME: "postgresql://grounded:grounded_local_password@localhost:5433/tpch",
}


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


def local_source_dsns(source_host_port: int = 5433) -> dict[str, str]:
    """Return the local development DSNs for a selected PostgreSQL host port."""
    return {
        SECRET_NAME: (
            "postgresql://grounded:grounded_local_password@"
            f"localhost:{source_host_port}/adventureworks"
        ),
        TPCH_SECRET_NAME: (
            "postgresql://grounded:grounded_local_password@"
            f"localhost:{source_host_port}/tpch"
        ),
    }


def ensure_local_source_dsns(path: Path = SECRETS_PATH, *, source_host_port: int = 5433) -> Path:
    """Fill missing local-development DSNs without replacing an existing choice."""
    existing: dict[str, object] = {}
    if path.exists():
        existing = tomllib.loads(path.read_text(encoding="utf-8"))
    defaults = local_source_dsns(source_host_port)
    values = {
        name: existing.get(name) if isinstance(existing.get(name), str) and existing[name] else default
        for name, default in defaults.items()
    }
    write_source_dsns(values, path)
    return path
