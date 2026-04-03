from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from app.models import AreaConfig, UserConfig

logger = logging.getLogger(__name__)

# /data is persistent in HA apps; fall back to local dir for development
STORE_DIR = Path(os.environ.get("DATA_DIR", "/data"))
STORE_PATH = STORE_DIR / "user_config.json"


class ConfigStore:
    """Persistent storage for user area configurations."""

    def load(self) -> UserConfig:
        """Load saved configuration from disk."""
        if not STORE_PATH.exists():
            return UserConfig()

        try:
            data = json.loads(STORE_PATH.read_text())
            areas = {}
            for area_id, config_data in data.get("areas", {}).items():
                areas[area_id] = AreaConfig(**config_data)
            return UserConfig(areas=areas)
        except Exception as e:
            logger.warning(f"Failed to load config from {STORE_PATH}: {e}")
            return UserConfig()

    def save(self, config: UserConfig) -> None:
        """Save configuration to disk."""
        try:
            STORE_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "areas": {
                    area_id: ac.model_dump()
                    for area_id, ac in config.areas.items()
                }
            }
            STORE_PATH.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save config to {STORE_PATH}: {e}")
            raise
