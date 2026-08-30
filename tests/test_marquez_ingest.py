from __future__ import annotations

import logging

import httpx

from ontology import marquez_client
from ontology.real_lineage import (
    GROUNDED_OL_PRODUCER,
    RUN_EVENT_SCHEMA_URL,
    _normalized_ingest_event,
)


def _run_event(event_type: str) -> dict:
    return {
        "eventType": event_type,
        "eventTime": "2026-08-16T00:00:00+00:00",
        "producer": f"{GROUNDED_OL_PRODUCER}/blob/main/infra/ingest.py",
        "schemaURL": RUN_EVENT_SCHEMA_URL,
        "run": {"runId": "f10bf37d-bc98-48d7-b340-2959a0d2fd06"},
        "job": {"namespace": "dlt", "name": "adventureworks_to_bronze"},
        "inputs": [{"namespace": "postgres", "name": "adventureworks"}],
        "outputs": [{"namespace": "bronze", "name": "salesorderdetail"}],
    }


def test_emit_events_posts_each_event_to_the_lineage_endpoint(monkeypatch):
    posted: list[tuple[str, dict]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

    class Client:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 5.0

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def post(self, url: str, *, json: dict) -> Response:
            posted.append((url, json))
            return Response()

    monkeypatch.setattr(marquez_client.httpx, "Client", Client)
    events = [_run_event("START"), _run_event("COMPLETE")]

    assert marquez_client.emit_events(events, base_url="http://marquez:5000/") is True
    assert posted == [
        ("http://marquez:5000/api/v1/lineage", events[0]),
        ("http://marquez:5000/api/v1/lineage", events[1]),
    ]
    assert all(event["producer"].startswith(GROUNDED_OL_PRODUCER) for _, event in posted)
    assert all(event["schemaURL"] == RUN_EVENT_SCHEMA_URL for _, event in posted)


def test_emit_events_warns_and_does_not_raise_when_marquez_is_unreachable(monkeypatch, caplog):
    class Client:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 5.0

        def __enter__(self):
            raise httpx.ConnectError("connection refused")

        def __exit__(self, *_args) -> None:
            return None

    monkeypatch.setattr(marquez_client.httpx, "Client", Client)

    with caplog.at_level(logging.WARNING):
        assert marquez_client.emit_events([{"eventType": "COMPLETE"}]) is False

    assert "Marquez is unavailable or rejected a lineage event" in caplog.text


def test_normalized_dlt_event_has_the_required_openlineage_producer_fields():
    event = _normalized_ingest_event(
        {
            "eventType": "COMPLETE",
            "eventTime": "2026-08-16T00:00:00+00:00",
            "run": {"runId": "f10bf37d-bc98-48d7-b340-2959a0d2fd06"},
            "job": {"namespace": "dlt", "name": "adventureworks_to_bronze"},
            "outputs": [{"namespace": "bronze", "name": "salesorderdetail"}],
        }
    )

    assert event["producer"] == f"{GROUNDED_OL_PRODUCER}/blob/main/infra/ingest.py"
    assert event["schemaURL"] == RUN_EVENT_SCHEMA_URL
