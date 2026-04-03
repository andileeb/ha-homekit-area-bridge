from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config_store import ConfigStore
from app.generator import generate_homekit_yaml
from app.ha_client import HAClient
from app.models import Area, AreaConfig, AreaSummary, ResolvedEntity, UserConfig
from app.resolver import build_area_summaries, resolve_entities, resolve_from_raw

logger = logging.getLogger(__name__)


class NormalizePathMiddleware:
    """Collapse consecutive slashes in the URL path.

    HA's ingress proxy sends ``//`` as the request path. FastAPI's
    ``@app.get("/")`` only matches a single ``/``, so the request 404s.
    This ASGI middleware rewrites ``//+`` → ``/`` before routing.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope["path"] = re.sub(r"//+", "/", scope["path"])
        await self.app(scope, receive, send)


def create_app(
    ha_client: HAClient | None = None,
    frontend_dir: Path | None = None,
    config_store: ConfigStore | None = None,
    ha_config_dir: Path | None = None,
    data_dir: Path | None = None,
) -> FastAPI:
    """
    Application factory. All dependencies are injectable for testing.
    """
    if ha_client is None:
        ha_client = HAClient()
    if frontend_dir is None:
        frontend_dir = Path(os.environ.get("FRONTEND_DIR", "/frontend"))
    if config_store is None:
        config_store = ConfigStore(data_dir=data_dir)
    if ha_config_dir is None:
        ha_config_dir = Path(os.environ.get("HA_CONFIG_DIR", "/homeassistant"))

    packages_dir = ha_config_dir / "packages"
    output_file = packages_dir / "homekit_area_bridge.yaml"

    # Cache for resolved data (refreshed on demand)
    cache: dict[str, object] = {}

    async def get_resolved_data() -> tuple[list[Area], dict[str, list[ResolvedEntity]]]:
        if "areas" not in cache:
            await refresh_data()
        return cache["areas"], cache["area_entities"]  # type: ignore[return-value]

    async def refresh_data() -> None:
        areas, area_entities = await resolve_entities(ha_client)
        cache["areas"] = areas
        cache["area_entities"] = area_entities

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            await ha_client.connect()
            logger.info("Connected to Home Assistant")
        except Exception as e:
            logger.warning(f"Could not connect to HA on startup: {e}")
        yield
        try:
            await ha_client.disconnect()
        except Exception:
            pass

    app = FastAPI(title="HomeKit Area Bridge", lifespan=lifespan)
    app.add_middleware(NormalizePathMiddleware)

    @app.middleware("http")
    async def ingress_middleware(request: Request, call_next):
        request.state.ingress_path = request.headers.get("X-Ingress-Path", "")
        response = await call_next(request)
        return response

    # ── Routes ──────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        ingress_path = request.state.ingress_path
        index_file = frontend_dir / "index.html"
        if not index_file.exists():
            return HTMLResponse(
                f"<h1>Frontend not found</h1><p>Expected at {index_file}</p>",
                status_code=500,
            )
        html = index_file.read_text()
        html = html.replace("__INGRESS_PATH__", ingress_path)
        return HTMLResponse(html)

    @app.get("/api/health")
    async def health():
        connected = ha_client._ws is not None and not ha_client._ws.closed
        return {"status": "ok", "ha_connected": connected}

    @app.get("/api/areas")
    async def get_areas() -> list[dict]:
        areas, area_entities = await get_resolved_data()
        summaries = build_area_summaries(areas, area_entities)
        return [s.model_dump() for s in summaries]

    @app.get("/api/areas/{area_id}/entities")
    async def get_area_entities(area_id: str) -> dict:
        areas, area_entities = await get_resolved_data()
        entities = area_entities.get(area_id, [])
        grouped: dict[str, list[dict]] = {}
        for e in entities:
            if e.domain not in grouped:
                grouped[e.domain] = []
            grouped[e.domain].append(e.model_dump())
        return {"area_id": area_id, "entities_by_domain": grouped}

    @app.get("/api/config")
    async def get_config() -> dict:
        config = config_store.load()
        return {"areas": {aid: ac.model_dump() for aid, ac in config.areas.items()}}

    @app.post("/api/config")
    async def save_config(config: UserConfig):
        config_store.save(config)
        return {"status": "ok"}

    @app.post("/api/generate")
    async def generate(config: UserConfig):
        areas, area_entities = await get_resolved_data()
        start_port = int(os.environ.get("HOMEKIT_START_PORT", "21100"))
        area_configs = list(config.areas.values())
        result = generate_homekit_yaml(area_configs, area_entities, start_port)
        return result.model_dump()

    @app.post("/api/apply")
    async def apply(config: UserConfig):
        areas, area_entities = await get_resolved_data()
        start_port = int(os.environ.get("HOMEKIT_START_PORT", "21100"))
        area_configs = list(config.areas.values())
        result = generate_homekit_yaml(area_configs, area_entities, start_port)

        if not result.bridges:
            return JSONResponse(
                status_code=400,
                content={"error": "No bridges to generate. Enable at least one area."},
            )

        packages_dir.mkdir(parents=True, exist_ok=True)
        output_file.write_text(result.yaml_content)
        logger.info(f"Wrote HomeKit config to {output_file}")
        config_store.save(config)

        return {
            "status": "ok",
            "file": str(output_file),
            "bridges": len(result.bridges),
            "message": "Configuration written. Restart Home Assistant to apply changes.",
        }

    @app.get("/api/status")
    async def status():
        ha_connected = ha_client._ws is not None and not ha_client._ws.closed
        packages_exists = packages_dir.exists()
        yaml_exists = output_file.exists()
        yaml_content = output_file.read_text() if yaml_exists else None
        return {
            "ha_connected": ha_connected,
            "packages_dir_exists": packages_exists,
            "yaml_exists": yaml_exists,
            "yaml_content": yaml_content,
            "output_file": str(output_file),
        }

    @app.post("/api/refresh")
    async def refresh():
        await refresh_data()
        return {"status": "ok"}

    # ── Static files (after all routes) ─────────────────────────

    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
    else:
        logger.warning(f"Frontend directory {frontend_dir} not found")

    return app


# Default app instance for uvicorn
app = create_app()