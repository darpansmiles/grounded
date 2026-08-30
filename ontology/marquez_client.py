"""Best-effort OpenLineage delivery to a local Marquez server."""

from __future__ import annotations

import logging
from typing import Any

import httpx

DEFAULT_MARQUEZ_URL = "http://localhost:5050"
GROUNDED_OL_PRODUCER = "https://github.com/grounded-flagship/grounded"
RUN_EVENT_SCHEMA_URL = "https://openlineage.io/spec/2-0-0/OpenLineage.json#/definitions/RunEvent"
_LOGGER = logging.getLogger(__name__)


def emit_events(
    events: list[dict[str, Any]], *, base_url: str = DEFAULT_MARQUEZ_URL
) -> bool:
    """Post OpenLineage events without making the local pipeline depend on Marquez."""
    endpoint = f"{base_url.rstrip('/')}/api/v1/lineage"
    try:
        with httpx.Client(timeout=5.0) as client:
            for event in events:
                response = client.post(endpoint, json=event)
                response.raise_for_status()
    except httpx.HTTPError as exc:
        _LOGGER.warning(
            "Marquez is unavailable or rejected a lineage event: %s",
            exc,
        )
        return False
    return True
