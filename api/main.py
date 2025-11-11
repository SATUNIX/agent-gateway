"""FastAPI application wiring routers, middleware, and dependencies."""

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.middleware import RequestContextMiddleware, RequestLoggingMiddleware
from api.metrics import PROMETHEUS_AVAILABLE, generate_prometheus_metrics
from api.routes import admin, chat, models
from config import get_settings
from observability.logging import configure_logging


class HealthResponse(BaseModel):
    status: str
    service: str


settings = get_settings()
logger = configure_logging(settings.log_level)

app = FastAPI(title=settings.project_name, version=settings.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RequestLoggingMiddleware, logger=logger)

app.include_router(chat.router)
app.include_router(models.router)
app.include_router(admin.router)

if settings.prometheus_enabled and PROMETHEUS_AVAILABLE:

    @app.get("/metrics/prometheus", include_in_schema=False)
    async def prometheus_metrics():
        payload, content_type = generate_prometheus_metrics()
        return Response(content=payload, media_type=content_type)


@app.get("/", response_model=HealthResponse, summary="Root welcome message")
async def root() -> HealthResponse:
    """Return a friendly message so front-ends know the gateway is alive."""
    return HealthResponse(status="ok", service="agent-gateway")


@app.get("/health", response_model=HealthResponse, summary="Health check endpoint")
async def health() -> HealthResponse:
    """Expose a dedicated health probe for orchestrators and monitoring."""
    return HealthResponse(status="ok", service="agent-gateway")
