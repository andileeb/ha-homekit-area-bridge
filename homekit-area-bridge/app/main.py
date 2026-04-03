from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config_store import ConfigStore
from app.generator import generate_homekit_yaml
from app.ha_client import HAClient
from app.models import Area, AreaConfig, AreaSummary, ResolvedEntity, UserConfig
from app.resolver import build_area_summaries, resolve_entities, resolve_from_raw

logger = logging.getLogger(__name__)

ha_client = HAClient()
config_store = ConfigStore()

# Path where HomeKit YAML config will be written
HA_CONFIG_DIR = Path(os.environ.get("HA_CONFIG_DIR", "/homeassistant"))
PACKAGES_DIR = HA_CONFIG_DIR / "packages"
OUTPUT_FILE = PACKAGES_DIR / "homekit_area_bridge.yaml"

# Cache for resolved data (refreshed on demand)
_cache: dict[str, object] = {}


async def _get_resolved_data() -> tuple[list[Area], dict[str, list[ResolvedEntity]]]:
    """Get resolved data, fetching from HA if not cached."""
    if "areas" not in _cache:
        await _refresh_data()
    return _cache["areas"], _cache["area_entities"]  # type: ignore[return-value]


async def _refresh_data() -> None:
    """Fetch fresh data from HA and update cache."""
    areas, area_entities = await resolve_entities(ha_client)
    _cache["areas"] = areas
    _cache["area_entities"] = area_entities


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to HA on startup, disconnect on shutdown."""
    try:
        await ha_client.connect()
        logger.info("Connected to Home Assistant")
    except Exception as e:
        logger.warning(f"Could not connect to HA on startup: {e}")
    yield
    await ha_client.disconnect()


app = FastAPI(title="HomeKit Area Bridge", lifespan=lifespan)


FRONTEND_DIR = Path("/frontend")


@app.middleware("http")
async def ingress_middleware(request: Request, call_next):
    """Extract X-Ingress-Path header and store it on request state."""
    request.state.ingress_path = request.headers.get("X-Ingress-Path", "")
    response = await call_next(request)
    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main UI with ingress path injected."""
    ingress_path = request.state.ingress_path
    index_file = FRONTEND_DIR / "index.html"
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
    """Health check endpoint."""
    connected = ha_client._ws is not None and not ha_client._ws.closed
    return {"status": "ok", "ha_connected": connected}


@app.get("/api/areas")
async def get_areas() -> list[dict]:
    """Return all areas with entity counts and domain breakdown."""
    areas, area_entities = await _get_resolved_data()
    summaries = build_area_summaries(areas, area_entities)
    return [s.model_dump() for s in summaries]


@app.get("/api/areas/{area_id}/entities")
async def get_area_entities(area_id: str) -> dict:
    """Return resolved entities for an area, grouped by domain."""
    areas, area_entities = await _get_resolved_data()
    entities = area_entities.get(area_id, [])

    grouped: dict[str, list[dict]] = {}
    for e in entities:
        if e.domain not in grouped:
            grouped[e.domain] = []
        grouped[e.domain].append(e.model_dump())

    return {"area_id": area_id, "entities_by_domain": grouped}


@app.get("/api/config")
async def get_config() -> dict:
    """Load saved user configuration."""
    config = config_store.load()
    return {"areas": {aid: ac.model_dump() for aid, ac in config.areas.items()}}


@app.post("/api/config")
async def save_config(config: UserConfig):
    """Save user configuration."""
    config_store.save(config)
    return {"status": "ok"}


@app.post("/api/generate")
async def generate(config: UserConfig):
    """Generate YAML preview from user configuration."""
    areas, area_entities = await _get_resolved_data()
    start_port = int(os.environ.get("HOMEKIT_START_PORT", "21100"))
    area_configs = list(config.areas.values())
    result = generate_homekit_yaml(area_configs, area_entities, start_port)
    return result.model_dump()


@app.post("/api/apply")
async def apply(config: UserConfig):
    """Generate YAML and write it to the HA packages directory."""
    areas, area_entities = await _get_resolved_data()
    start_port = int(os.environ.get("HOMEKIT_START_PORT", "21100"))
    area_configs = list(config.areas.values())
    result = generate_homekit_yaml(area_configs, area_entities, start_port)

    if not result.bridges:
        return JSONResponse(
            status_code=400,
            content={"error": "No bridges to generate. Enable at least one area."},
        )

    # Ensure packages directory exists
    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Write YAML
    OUTPUT_FILE.write_text(result.yaml_content)
    logger.info(f"Wrote HomeKit config to {OUTPUT_FILE}")

    # Also persist user config
    config_store.save(config)

    return {
        "status": "ok",
        "file": str(OUTPUT_FILE),
        "bridges": len(result.bridges),
        "message": "Configuration written. Restart Home Assistant to apply changes.",
    }


@app.get("/api/status")
async def status():
    """Check system status: packages dir, existing YAML, connection."""
    ha_connected = ha_client._ws is not None and not ha_client._ws.closed
    packages_exists = PACKAGES_DIR.exists()
    yaml_exists = OUTPUT_FILE.exists()
    yaml_content = OUTPUT_FILE.read_text() if yaml_exists else None

    return {
        "ha_connected": ha_connected,
        "packages_dir_exists": packages_exists,
        "yaml_exists": yaml_exists,
        "yaml_content": yaml_content,
        "output_file": str(OUTPUT_FILE),
    }


@app.post("/api/refresh")
async def refresh():
    """Re-fetch data from HA registries."""
    await _refresh_data()
    return {"status": "ok"}


# Mount static files AFTER all routes so a mount failure can't prevent route registration
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
else:
    logger.warning(f"Frontend directory {FRONTEND_DIR} not found, static files unavailable")
