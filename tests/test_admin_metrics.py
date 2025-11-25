from __future__ import annotations

from fastapi.testclient import TestClient

import api.main as main_app
from api.metrics import record_dropin_failure, metrics


DEV_HEADERS = {"x-api-key": "dev-secret"}


def test_admin_metrics_exposes_tool_and_dropin_data():
    record_dropin_failure(kind="discovery_validation")
    metrics.record_tool_invocation(
        tool_name="sample",
        provider="local",
        latency_ms=5.0,
        success=True,
        source="sdk",
    )
    client = TestClient(main_app.app)
    response = client.get("/admin/metrics", headers=DEV_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert "tool_breakdown" in payload
    assert "dropin_failures" in payload
    assert "sample" in payload["tool_breakdown"]
    assert payload["dropin_failures"].get("discovery_validation", 0) >= 1
