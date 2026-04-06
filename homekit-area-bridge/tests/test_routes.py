"""Test all API routes using FastAPI TestClient with mocked HA client."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.ha_client import HAClient
from app.main import create_app
from app.resolver import resolve_from_raw

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


class MockHAClient(HAClient):
    """HA client that returns mock data instead of connecting to HA."""

    def __init__(self, areas=None, devices=None, entities=None):
        self._areas = areas or []
        self._devices = devices or []
        self._entities = entities or []
        self._ws = None
        self._msg_id = 0
        self.token = "mock-token"
        self.ws_url = "ws://mock/core/websocket"
        self.rest_url = "http://mock/core/api"

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def get_areas(self):
        return self._areas

    async def get_devices(self):
        return self._devices

    async def get_entities(self):
        return self._entities

    async def fetch_all(self):
        return self._areas, self._devices, self._entities


@pytest.fixture
def mock_ha_data():
    """Realistic mock HA registry data."""
    areas = [
        {"area_id": "kitchen", "name": "Kitchen", "icon": None, "floor_id": None, "aliases": []},
        {"area_id": "living_room", "name": "Living Room", "icon": None, "floor_id": None, "aliases": []},
    ]
    devices = [
        {"id": "dev1", "area_id": "kitchen", "name": "Hub", "name_by_user": None, "disabled_by": None},
    ]
    entities = [
        {
            "entity_id": "light.kitchen_ceiling",
            "unique_id": "u1",
            "platform": "hue",
            "area_id": "kitchen",
            "device_id": None,
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Kitchen Ceiling",
            "name": None,
            "entity_category": None,
        },
        {
            "entity_id": "switch.kitchen_coffee",
            "unique_id": "u2",
            "platform": "shelly",
            "area_id": None,
            "device_id": "dev1",
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Coffee Machine",
            "name": None,
            "entity_category": None,
        },
        {
            "entity_id": "light.living_room_main",
            "unique_id": "u3",
            "platform": "hue",
            "area_id": "living_room",
            "device_id": None,
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Main Light",
            "name": None,
            "entity_category": None,
        },
    ]
    return areas, devices, entities


@pytest.fixture
def client(mock_ha_data, tmp_path):
    """TestClient with mocked HA data and local frontend."""
    areas, devices, entities = mock_ha_data
    ha_client = MockHAClient(areas=areas, devices=devices, entities=entities)
    application = create_app(
        ha_client=ha_client,
        frontend_dir=FRONTEND_DIR,
        ha_config_dir=tmp_path / "ha_config",
        data_dir=tmp_path / "data",
    )
    with TestClient(application) as c:
        yield c


@pytest.fixture
def client_with_ingress(mock_ha_data, tmp_path):
    """TestClient that sends X-Ingress-Path header like HA Supervisor does."""
    areas, devices, entities = mock_ha_data
    ha_client = MockHAClient(areas=areas, devices=devices, entities=entities)
    application = create_app(
        ha_client=ha_client,
        frontend_dir=FRONTEND_DIR,
        ha_config_dir=tmp_path / "ha_config",
        data_dir=tmp_path / "data",
    )
    with TestClient(application) as c:
        c._ingress_path = "/api/hassio_ingress/test_token"
        yield c


# ── Index route ─────────────────────────────────────────────────

class TestIndex:
    def test_get_root_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "HomeKit Area Bridge" in resp.text

    def test_get_root_with_trailing_slash(self, client):
        resp = client.get("/", follow_redirects=True)
        assert resp.status_code == 200

    def test_ingress_path_injected(self, client):
        resp = client.get("/", headers={"X-Ingress-Path": "/api/hassio_ingress/TOKEN123"})
        assert resp.status_code == 200
        assert "/api/hassio_ingress/TOKEN123" in resp.text
        assert "__INGRESS_PATH__" not in resp.text

    def test_get_double_slash_returns_html(self, client):
        """HA ingress proxy sends // as the path — must still serve index."""
        resp = client.get("//")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "HomeKit Area Bridge" in resp.text

    def test_empty_ingress_path(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        # base href should be empty string + /
        assert "__INGRESS_PATH__" not in resp.text

    def test_missing_frontend_returns_500(self, mock_ha_data, tmp_path):
        areas, devices, entities = mock_ha_data
        ha_client = MockHAClient(areas=areas, devices=devices, entities=entities)
        application = create_app(
            ha_client=ha_client,
            frontend_dir=tmp_path / "nonexistent",
            ha_config_dir=tmp_path / "ha_config",
            data_dir=tmp_path / "data",
        )
        with TestClient(application) as c:
            resp = c.get("/")
            assert resp.status_code == 500
            assert "Frontend not found" in resp.text


# ── Health ──────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "ha_connected" in data


# ── Areas ───────────────────────────────────────────────────────

class TestAreas:
    def test_get_areas(self, client):
        resp = client.get("/api/areas")
        assert resp.status_code == 200
        areas = resp.json()
        assert len(areas) == 2
        names = {a["name"] for a in areas}
        assert names == {"Kitchen", "Living Room"}

    def test_area_has_entity_counts(self, client):
        resp = client.get("/api/areas")
        areas = resp.json()
        kitchen = next(a for a in areas if a["area_id"] == "kitchen")
        assert kitchen["homekit_entity_count"] == 2  # light + switch
        assert kitchen["domain_counts"]["light"] == 1
        assert kitchen["domain_counts"]["switch"] == 1


# ── Area entities ───────────────────────────────────────────────

class TestAreaEntities:
    def test_get_area_entities(self, client):
        resp = client.get("/api/areas/kitchen/entities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["area_id"] == "kitchen"
        assert "light" in data["entities_by_domain"]
        assert "switch" in data["entities_by_domain"]

    def test_nonexistent_area_returns_empty(self, client):
        resp = client.get("/api/areas/nonexistent/entities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entities_by_domain"] == {}


# ── Config persistence ──────────────────────────────────────────

class TestConfig:
    def test_get_config_empty_initially(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        assert resp.json()["areas"] == {}

    def test_save_and_load_config(self, client):
        config = {
            "areas": {
                "kitchen": {
                    "area_id": "kitchen",
                    "enabled": True,
                    "bridge_name": "Kitchen Bridge",
                    "mode": "all_domains",
                    "include_domains": [],
                    "include_entities": [],
                    "exclude_entities": [],
                }
            }
        }
        resp = client.post("/api/config", json=config)
        assert resp.status_code == 200

        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "kitchen" in data["areas"]
        assert data["areas"]["kitchen"]["enabled"] is True


# ── Generate ────────────────────────────────────────────────────

class TestGenerate:
    def test_generate_preview(self, client):
        config = {
            "areas": {
                "kitchen": {
                    "area_id": "kitchen",
                    "enabled": True,
                    "bridge_name": "Kitchen Bridge",
                    "mode": "all_domains",
                    "include_domains": [],
                    "include_entities": [],
                    "exclude_entities": [],
                }
            }
        }
        resp = client.post("/api/generate", json=config)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["bridges"]) == 1
        assert data["bridges"][0]["name"] == "Kitchen Bridge"
        assert "yaml_content" in data
        assert "homekit:" in data["yaml_content"]
        # Diff fields present
        assert "has_changes" in data
        assert "diff" in data
        assert "current_yaml" in data
        # No file on disk yet, so everything is new
        assert data["has_changes"] is True
        assert data["current_yaml"] == ""

    def test_generate_diff_with_existing_file(self, mock_ha_data, tmp_path):
        """Diff should show changes when an existing YAML file differs."""
        areas, devices, entities = mock_ha_data
        ha_config_dir = tmp_path / "ha_config"
        packages_dir = ha_config_dir / "packages"
        packages_dir.mkdir(parents=True)
        (packages_dir / "homekit_area_bridge.yaml").write_text("old: content\n")
        ha_client = MockHAClient(areas=areas, devices=devices, entities=entities)
        application = create_app(
            ha_client=ha_client,
            frontend_dir=FRONTEND_DIR,
            ha_config_dir=ha_config_dir,
            data_dir=tmp_path / "data",
        )
        with TestClient(application) as c:
            config = {
                "areas": {
                    "kitchen": {
                        "area_id": "kitchen",
                        "enabled": True,
                        "bridge_name": "Kitchen Bridge",
                        "mode": "all_domains",
                        "include_domains": [],
                        "include_entities": [],
                        "exclude_entities": [],
                    }
                }
            }
            resp = c.post("/api/generate", json=config)
            data = resp.json()
            assert data["has_changes"] is True
            assert data["current_yaml"] == "old: content\n"
            assert "-old: content" in data["diff"]
            assert "+homekit:" in data["diff"] or "+ " in data["diff"]

    def test_generate_no_enabled_areas(self, client):
        config = {
            "areas": {
                "kitchen": {
                    "area_id": "kitchen",
                    "enabled": False,
                    "bridge_name": "Kitchen Bridge",
                    "mode": "all_domains",
                    "include_domains": [],
                    "include_entities": [],
                    "exclude_entities": [],
                }
            }
        }
        resp = client.post("/api/generate", json=config)
        assert resp.status_code == 200
        assert resp.json()["bridges"] == []


# ── Apply ───────────────────────────────────────────────────────

class TestApply:
    def test_apply_writes_yaml(self, client, tmp_path):
        config = {
            "areas": {
                "kitchen": {
                    "area_id": "kitchen",
                    "enabled": True,
                    "bridge_name": "Kitchen Bridge",
                    "mode": "all_domains",
                    "include_domains": [],
                    "include_entities": [],
                    "exclude_entities": [],
                }
            }
        }
        resp = client.post("/api/apply", json=config)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["bridges"]) == 1
        assert data["bridges"][0]["name"] == "Kitchen Bridge"
        assert data["bridges"][0]["port"] == 21100
        assert data["entity_count_per_bridge"]["Kitchen Bridge"] == 2
        assert data["packages_configured"] is False

    def test_apply_returns_multi_bridge_details(self, client, tmp_path):
        config = {
            "areas": {
                "kitchen": {
                    "area_id": "kitchen",
                    "enabled": True,
                    "bridge_name": "Kitchen Bridge",
                    "mode": "all_domains",
                    "include_domains": [],
                    "include_entities": [],
                    "exclude_entities": [],
                },
                "living_room": {
                    "area_id": "living_room",
                    "enabled": True,
                    "bridge_name": "Living Room Bridge",
                    "mode": "all_domains",
                    "include_domains": [],
                    "include_entities": [],
                    "exclude_entities": [],
                },
            }
        }
        resp = client.post("/api/apply", json=config)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["bridges"]) == 2
        names = {b["name"] for b in data["bridges"]}
        assert "Kitchen Bridge" in names
        assert "Living Room Bridge" in names
        assert data["entity_count_per_bridge"]["Kitchen Bridge"] == 2
        assert data["entity_count_per_bridge"]["Living Room Bridge"] == 1

    def test_apply_packages_configured_true(self, mock_ha_data, tmp_path):
        """packages_configured should be True when configuration.yaml has packages."""
        areas, devices, entities = mock_ha_data
        ha_config_dir = tmp_path / "ha_config"
        ha_config_dir.mkdir()
        (ha_config_dir / "configuration.yaml").write_text(
            "homeassistant:\n  packages: !include_dir_named packages\n"
        )
        ha_client = MockHAClient(areas=areas, devices=devices, entities=entities)
        application = create_app(
            ha_client=ha_client,
            frontend_dir=FRONTEND_DIR,
            ha_config_dir=ha_config_dir,
            data_dir=tmp_path / "data",
        )
        with TestClient(application) as c:
            config = {
                "areas": {
                    "kitchen": {
                        "area_id": "kitchen",
                        "enabled": True,
                        "bridge_name": "Kitchen Bridge",
                        "mode": "all_domains",
                        "include_domains": [],
                        "include_entities": [],
                        "exclude_entities": [],
                    }
                }
            }
            resp = c.post("/api/apply", json=config)
            assert resp.status_code == 200
            assert resp.json()["packages_configured"] is True

    def test_apply_no_bridges_returns_400(self, client):
        config = {"areas": {}}
        resp = client.post("/api/apply", json=config)
        assert resp.status_code == 400


# ── Status ──────────────────────────────────────────────────────

class TestStatus:
    def test_status(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "ha_connected" in data
        assert "yaml_exists" in data


# ── Refresh ─────────────────────────────────────────────────────

class TestRefresh:
    def test_refresh(self, client):
        resp = client.post("/api/refresh")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── Static files ────────────────────────────────────────────────

class TestStaticFiles:
    def test_css_served(self, client):
        resp = client.get("/static/styles.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers["content-type"]

    def test_js_served(self, client):
        resp = client.get("/static/app.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]

    def test_nonexistent_static_returns_404(self, client):
        resp = client.get("/static/nonexistent.xyz")
        assert resp.status_code == 404