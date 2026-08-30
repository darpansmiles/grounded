"""Read and append governed-operation audit records as JSONL."""

from __future__ import annotations

import json
from pathlib import Path


def append_audit(record: dict, path: str = "audit.log.jsonl") -> None:
    """Append exactly one JSON object without rewriting existing audit records."""
    with Path(path).open("a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(record, default=str, sort_keys=True))
        audit_file.write("\n")


def read_audit(path: str) -> list[dict]:
    """Read append-only audit JSONL records for inspection and tests."""
    audit_path = Path(path)
    if not audit_path.exists():
        return []
    with audit_path.open(encoding="utf-8") as audit_file:
        return [json.loads(line) for line in audit_file if line.strip()]
