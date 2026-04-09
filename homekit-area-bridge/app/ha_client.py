from __future__ import annotations

import asyncio
import json
import logging
import os

import aiohttp
import websockets

logger = logging.getLogger(__name__)


class HAClientError(Exception):
    pass


class HAClient:
    """Client for communicating with Home Assistant via WebSocket and REST APIs."""

    def __init__(self) -> None:
        self.ws_url = "ws://supervisor/core/websocket"
        self.rest_url = "http://supervisor/core/api"
        self.token = os.environ.get("SUPERVISOR_TOKEN", "")
        self._ws: websockets.ClientConnection | None = None
        self._msg_id = 0

    async def connect(self) -> None:
        """Establish and authenticate WebSocket connection."""
        if not self.token:
            raise HAClientError(
                "SUPERVISOR_TOKEN not found. "
                "Ensure homeassistant_api and hassio_api are enabled in config.yaml."
            )

        logger.info("Connecting to Home Assistant WebSocket API...")
        self._ws = await websockets.connect(self.ws_url)

        # Receive auth_required
        msg = json.loads(await self._ws.recv())
        if msg.get("type") != "auth_required":
            raise HAClientError(f"Expected auth_required, got: {msg.get('type')}")

        # Send auth
        await self._ws.send(json.dumps({
            "type": "auth",
            "access_token": self.token,
        }))

        # Receive auth_ok
        msg = json.loads(await self._ws.recv())
        if msg.get("type") != "auth_ok":
            raise HAClientError(f"Authentication failed: {msg}")

        logger.info("WebSocket authenticated successfully")

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _ensure_connected(self) -> None:
        """Reconnect if not connected."""
        if self._ws is None or self._ws.closed:
            await self.connect()

    async def _send_command(self, msg_type: str, **kwargs: object) -> object:
        """Send a WebSocket command and return the result."""
        await self._ensure_connected()
        assert self._ws is not None

        self._msg_id += 1
        payload = {"id": self._msg_id, "type": msg_type, **kwargs}
        await self._ws.send(json.dumps(payload))

        response = json.loads(await self._ws.recv())
        if not response.get("success"):
            raise HAClientError(
                f"Command {msg_type} failed: {response.get('error', response)}"
            )
        return response["result"]

    async def get_areas(self) -> list[dict]:
        """Fetch area registry via WebSocket."""
        result = await self._send_command("config/area_registry/list")
        return result  # type: ignore[return-value]

    async def get_devices(self) -> list[dict]:
        """Fetch device registry via WebSocket."""
        result = await self._send_command("config/device_registry/list")
        return result  # type: ignore[return-value]

    async def get_entities(self) -> list[dict]:
        """Fetch entity registry via WebSocket."""
        result = await self._send_command("config/entity_registry/list")
        return result  # type: ignore[return-value]

    async def get_states(self) -> list[dict]:
        """Fetch all entity states via REST API."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.rest_url}/states", headers=headers
            ) as resp:
                if resp.status != 200:
                    raise HAClientError(
                        f"Failed to fetch states: HTTP {resp.status}"
                    )
                return await resp.json()

    async def restart_ha(self) -> bool:
        """Trigger a Home Assistant restart via the REST API.

        Uses REST rather than WebSocket because the WS connection will be
        severed during the restart process.
        """
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.rest_url}/services/homeassistant/restart",
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    raise HAClientError(
                        f"Failed to trigger restart: HTTP {resp.status}"
                    )
                return True

    async def fetch_all(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Fetch areas, devices, and entities in parallel."""
        await self._ensure_connected()
        # Send all three commands sequentially but quickly
        # (WebSocket requires sequential send/recv for message correlation)
        areas = await self.get_areas()
        devices = await self.get_devices()
        entities = await self.get_entities()
        return areas, devices, entities
