from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import duckdb

import packlib
from agent.ungoverned import pack_schema_prompt
from infra import ingest
from ontology import real_lineage


def _sqlite_pack(tmp_path: Path, monkeypatch) -> packlib.Pack:
    """Create a disposable SQLite, no-transform pack with a Cube capability."""
    monkeypatch.setattr(packlib, "PROJECT_ROOT", tmp_path)
    packs_directory = tmp_path / "datasets"
    monkeypatch.setattr(packlib, "PACKS_DIRECTORY", packs_directory)
    pack_root = packs_directory / "sqlite_no_transform"
    (pack_root / "source").mkdir(parents=True)
    (pack_root / "semantics" / "cube").mkdir(parents=True)
    (pack_root / "semantics" / "cube" / "model").mkdir()
    source_path = pack_root / "source" / "sample.sqlite"
    with sqlite3.connect(source_path) as source:
        source.execute("CREATE TABLE regions (region TEXT, amount REAL)")
        source.executemany(
            "INSERT INTO regions VALUES (?, ?)", [("EU", 12.5), ("US", 7.5)]
        )
    (pack_root / "pack.yml").write_text(
        """
name: sqlite_no_transform
lineage_namespace: sqlite_no_transform
source:
  type: sqlite
  path: source/sample.sqlite
  tables: [regions]
destination:
  type: duckdb
  path: data/sqlite_no_transform.duckdb
  dataset: bronze
semantics:
  backend: cube
  cube: semantics/cube
  metrics: [semantics/total_amount.yml]
golden: golden.yml
""".lstrip(),
        encoding="utf-8",
    )
    (pack_root / "semantics" / "total_amount.yml").write_text(
        "metric: total_amount\n",
        encoding="utf-8",
    )
    (pack_root / "golden.yml").write_text("[]\n", encoding="utf-8")
    monkeypatch.setenv("GROUNDED_PACK", "sqlite_no_transform")
    return packlib.active_pack()


def test_sqlite_no_transform_pack_ingests_prompts_and_emits_source_lineage(
    tmp_path, monkeypatch
):
    pack = _sqlite_pack(tmp_path, monkeypatch)
    lineage_path = tmp_path / "ingest.jsonl"
    monkeypatch.setattr(ingest, "LINEAGE_PATH", lineage_path)

    ingest.ingest()
    ingest.verify()

    with duckdb.connect(str(pack.destination.path), read_only=True) as destination:
        assert destination.execute(
            "SELECT * FROM bronze.regions ORDER BY region"
        ).fetchall() == [("EU", 12.5), ("US", 7.5)]
    prompt = pack_schema_prompt(str(pack.destination.path), pack.name, has_transform=False)
    assert "sqlite_no_transform bronze schema" in prompt
    assert "bronze.regions(region, amount)" in prompt

    captured: list[dict] = []
    monkeypatch.setattr(real_lineage, "emit_events", lambda events: captured.extend(events) or 1)
    result = real_lineage.emit_real_lineage(ingest_path=lineage_path)

    assert result == {
        "events_emitted": 2,
        "ingest_events_emitted": 2,
        "sqlmesh_events_emitted": 0,
        "marquez_delivered": 1,
    }
    complete = json.loads(lineage_path.read_text(encoding="utf-8").splitlines()[-1])
    assert complete["job"]["namespace"] == "sqlite_no_transform.sqlite"
    assert complete["inputs"][0]["namespace"] == "sqlite_no_transform.sqlite"
    assert complete["inputs"][0]["name"] == "regions"
    assert complete["outputs"][0]["namespace"] == "sqlite_no_transform.bronze"
    assert captured == [
        real_lineage._normalized_ingest_event(json.loads(line))
        for line in lineage_path.read_text(encoding="utf-8").splitlines()
    ]


def test_sqlite_source_path_is_safe_but_need_not_exist(tmp_path, monkeypatch):
    pack = _sqlite_pack(tmp_path, monkeypatch)
    manifest = pack.root / "pack.yml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "source/sample.sqlite", "source/not-yet-fetched.sqlite"
        ),
        encoding="utf-8",
    )

    loaded = packlib.active_pack()

    assert loaded.source.path == pack.root / "source" / "not-yet-fetched.sqlite"
    assert not packlib.source_is_available(loaded)
