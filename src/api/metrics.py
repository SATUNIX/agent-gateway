"""Simple in-memory metrics collector with Prometheus support."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Tuple

try:
    from prometheus_client import (  # type: ignore
        CollectorRegistry,
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except Exception:  # noqa: BLE001
    CollectorRegistry = None  # type: ignore
    Counter = None  # type: ignore
    Histogram = None  # type: ignore
    generate_latest = None  # type: ignore
    CONTENT_TYPE_LATEST = "text/plain"
    PROMETHEUS_AVAILABLE = False


@dataclass
class GatewayMetrics:
    total_requests: int = 0
    streaming_requests: int = 0
    total_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = field(default=float("inf"))
    tool_invocations: int = 0
    tool_failures: int = 0
    tool_latency_ms: float = 0.0
    tool_breakdown: Dict[str, Dict[str, Dict[str, float]]] = field(default_factory=dict)
    dropin_failure_counts: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._lock = Lock()

    def record_completion(self, latency_ms: float, streaming: bool) -> None:
        with self._lock:
            self.total_requests += 1
            if streaming:
                self.streaming_requests += 1
            self.total_latency_ms += latency_ms
            self.max_latency_ms = max(self.max_latency_ms, latency_ms)
            self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        _prometheus_record_completion(latency_ms, streaming)

    def record_tool_invocation(
        self,
        *,
        tool_name: str,
        provider: str,
        latency_ms: float,
        success: bool,
        source: str,
    ) -> None:
        with self._lock:
            self.tool_invocations += 1
            if not success:
                self.tool_failures += 1
            self.tool_latency_ms += latency_ms
            tool_sources = self.tool_breakdown.setdefault(tool_name, {})
            source_stats = tool_sources.setdefault(
                source,
                {"provider": provider, "count": 0, "failures": 0, "latency_ms": 0.0},
            )
            source_stats["count"] += 1
            source_stats["latency_ms"] += latency_ms
            if not success:
                source_stats["failures"] += 1
        _prometheus_record_tool(tool_name, provider, latency_ms, success, source)

    def record_dropin_failure(self, *, kind: str) -> None:
        with self._lock:
            self.dropin_failure_counts[kind] = self.dropin_failure_counts.get(kind, 0) + 1
        _prometheus_record_dropin_failure(kind)

    def snapshot(self) -> Dict[str, float]:
        with self._lock:
            avg_latency = (
                self.total_latency_ms / self.total_requests
                if self.total_requests
                else 0.0
            )
            avg_tool_latency = (
                self.tool_latency_ms / self.tool_invocations
                if self.tool_invocations
                else 0.0
            )
            min_latency = self.min_latency_ms if self.total_requests else 0.0
            return {
                "total_requests": self.total_requests,
                "streaming_requests": self.streaming_requests,
                "average_latency_ms": round(avg_latency, 3),
                "max_latency_ms": round(self.max_latency_ms, 3),
                "min_latency_ms": round(min_latency, 3),
                "tool_invocations": self.tool_invocations,
                "tool_failures": self.tool_failures,
                "average_tool_latency_ms": round(avg_tool_latency, 3),
                "tool_breakdown": self.tool_breakdown,
                "dropin_failures": self.dropin_failure_counts,
            }


metrics = GatewayMetrics()


if PROMETHEUS_AVAILABLE:
    PROM_REGISTRY = CollectorRegistry()
    REQUEST_COUNTER = Counter(
        "agent_gateway_requests_total",
        "Count of chat completion requests",
        labelnames=("streaming",),
        registry=PROM_REGISTRY,
    )
    REQUEST_LATENCY = Histogram(
        "agent_gateway_request_latency_ms",
        "Latency of chat completion requests in milliseconds",
        registry=PROM_REGISTRY,
        buckets=(25, 50, 100, 200, 400, 800, 1600, float("inf")),
    )
    TOOL_COUNTER = Counter(
        "agent_gateway_tool_invocations_total",
        "Count of tool invocations",
        labelnames=("tool", "provider", "status", "source"),
        registry=PROM_REGISTRY,
    )
    TOOL_LATENCY = Histogram(
        "agent_gateway_tool_latency_ms",
        "Latency of tool invocations in milliseconds",
        labelnames=("tool", "provider", "source"),
        registry=PROM_REGISTRY,
        buckets=(10, 25, 50, 100, 250, 500, 1000, float("inf")),
    )
    UPSTREAM_COUNTER = Counter(
        "agent_gateway_upstream_requests_total",
        "Count of upstream calls",
        labelnames=("upstream", "status"),
        registry=PROM_REGISTRY,
    )
    UPSTREAM_LATENCY = Histogram(
        "agent_gateway_upstream_latency_ms",
        "Latency of upstream calls in milliseconds",
        labelnames=("upstream",),
        registry=PROM_REGISTRY,
        buckets=(25, 50, 100, 200, 400, 800, 1600, float("inf")),
    )
else:
    PROM_REGISTRY = None
    REQUEST_COUNTER = None
    REQUEST_LATENCY = None
    TOOL_COUNTER = None
    TOOL_LATENCY = None
    UPSTREAM_COUNTER = None
    UPSTREAM_LATENCY = None
    DROPIN_FAILURE_COUNTER = None


def _prometheus_record_completion(latency_ms: float, streaming: bool) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    REQUEST_COUNTER.labels(streaming=str(streaming).lower()).inc()
    REQUEST_LATENCY.observe(latency_ms)


def _prometheus_record_tool(
    tool: str, provider: str, latency_ms: float, success: bool, source: str
) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    status = "success" if success else "failure"
    TOOL_COUNTER.labels(tool=tool, provider=provider, status=status, source=source).inc()
    TOOL_LATENCY.labels(tool=tool, provider=provider, source=source).observe(latency_ms)


def record_upstream_call(upstream: str, latency_ms: float, success: bool) -> None:
    status = "success" if success else "failure"
    if UPSTREAM_COUNTER is not None and UPSTREAM_LATENCY is not None:
        UPSTREAM_COUNTER.labels(upstream=upstream, status=status).inc()
        UPSTREAM_LATENCY.labels(upstream=upstream).observe(latency_ms)


if PROMETHEUS_AVAILABLE:
    DROPIN_FAILURE_COUNTER = Counter(
        "agent_gateway_dropin_failures_total",
        "Count of drop-in related failures",
        labelnames=("kind",),
        registry=PROM_REGISTRY,
    )
else:
    DROPIN_FAILURE_COUNTER = None


def _prometheus_record_dropin_failure(kind: str) -> None:
    if DROPIN_FAILURE_COUNTER is not None:
        DROPIN_FAILURE_COUNTER.labels(kind=kind).inc()


def record_dropin_failure(kind: str) -> None:
    metrics.record_dropin_failure(kind=kind)

def generate_prometheus_metrics() -> Tuple[bytes, str]:
    if not PROMETHEUS_AVAILABLE or PROM_REGISTRY is None:
        raise RuntimeError("prometheus_client is not available")
    return generate_latest(PROM_REGISTRY), CONTENT_TYPE_LATEST
