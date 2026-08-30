from __future__ import annotations

import json
from pathlib import Path

import pytest

from ontology import real_lineage
from packlib import load_pack

_ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    not (_ROOT / real_lineage.DEFAULT_INGEST_LINEAGE_PATH).is_file(),
    reason="real-lineage tests require the local Slice 029 dlt JSONL artifact",
)


def test_ingest_events_are_normalized_from_the_producer_jsonl():
    raw_events = [
        json.loads(line)
        for line in (_ROOT / real_lineage.DEFAULT_INGEST_LINEAGE_PATH)
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    events = real_lineage.ingest_events(_ROOT / real_lineage.DEFAULT_INGEST_LINEAGE_PATH)
    pack_name = raw_events[0]["job"]["namespace"].removesuffix(".dlt")

    assert [event["job"]["namespace"] for event in raw_events] == [
        f"{pack_name}.dlt",
        f"{pack_name}.dlt",
    ]
    raw_inputs = {
        (dataset["namespace"], dataset["name"]): dataset
        for dataset in raw_events[-1]["inputs"]
    }
    raw_outputs = {
        (dataset["namespace"], dataset["name"]): dataset
        for dataset in raw_events[-1]["outputs"]
    }
    assert raw_inputs
    assert raw_outputs
    assert all(namespace == f"{pack_name}.postgres" for namespace, _ in raw_inputs)
    assert all(namespace == f"{pack_name}.bronze" for namespace, _ in raw_outputs)
    assert all(output["facets"]["schema"]["fields"] for output in raw_outputs.values())
    assert all(
        output["facets"]["dataQualityMetrics"]["rowCount"] > 0
        for output in raw_outputs.values()
    )
    assert [event["eventType"] for event in events] == ["START", "COMPLETE"]
    assert all(
        dataset["namespace"] == f"{pack_name}.postgres"
        and "." in dataset["name"]
        for event in events
        for dataset in event["inputs"]
    )
    assert all(
        dataset["namespace"] == f"{pack_name}.bronze"
        for dataset in events[-1]["outputs"]
    )


def test_real_lineage_emits_dlt_and_sqlmesh_events_to_marquez(monkeypatch):
    captured: list[dict] = []

    def capture_events(events: list[dict]) -> bool:
        captured.extend(events)
        return True

    monkeypatch.setattr(real_lineage, "emit_events", capture_events)
    raw_event = json.loads(
        (_ROOT / real_lineage.DEFAULT_INGEST_LINEAGE_PATH).read_text(encoding="utf-8").splitlines()[0]
    )
    pack_name = raw_event["job"]["namespace"].removesuffix(".dlt")
    pack = load_pack(pack_name)
    assert pack.transform_dir is not None
    monkeypatch.setenv("GROUNDED_PACK", pack_name)
    try:
        result = real_lineage.emit_real_lineage(
            ingest_path=_ROOT / real_lineage.DEFAULT_INGEST_LINEAGE_PATH,
            transform_path=pack.transform_dir,
        )
    except PermissionError as exc:
        pytest.skip(f"SQLMesh lineage API needs local process-worker permissions: {exc}")

    assert result["ingest_events_emitted"] == 2
    assert result["sqlmesh_events_emitted"] > 0
    assert result["events_emitted"] == len(captured)
    assert result["marquez_delivered"] is True
    assert {event["job"]["namespace"] for event in captured} == {
        f"{pack_name}.dlt",
        f"{pack_name}.sqlmesh",
    }
