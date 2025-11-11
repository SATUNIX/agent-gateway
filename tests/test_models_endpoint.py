from __future__ import annotations

from api.routes import models
from registry.models import AgentSpec


def test_serialize_spec_includes_metadata():
    spec = AgentSpec(
        name="echo",
        namespace="demo",
        display_name="Echo Agent",
        description="Echo",
        kind="sdk",
        upstream="lmstudio",
        model="gpt-4o-mini",
        module="agents.echo:agent",
        metadata={"discovered_at": 1234567890, "dropin": True},
    )

    info = models._serialize_spec(spec)

    assert info.id == "demo/echo"
    assert info.created == 1234567890
    assert info.metadata["dropin"] is True
    assert info.metadata["namespace"] == "demo"
