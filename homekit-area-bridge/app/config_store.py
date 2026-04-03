from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from app.models import AreaConfig, UserConfig

logger = logging.getLogger(__name__)


class ConfigStore:
    """Persistent storage for user area configurations."""

    def __init__(self, data_dir: Path | None = None) -> None:
        # /data is persistent in HA apps; fall back to local dir for development
        self._dir = data_dir or Path(os.environ.get("DATA_DIR", "/data"))
        self._path = self._dir / "user_config.json"

    def load(self) -> UserConfig:
        """Load saved configuration from disk."""
        if not self._path.exists():
            return UserConfig()

        try:
            data = json.loads(self._path.read_text())
            areas = {}
            for area_id, config_data in data.get("areas", {}).items():
                areas[area_id] = AreaConfig(**config_data)
            return UserConfig(areas=areas)
        except Exception as e:
            logger.warning(f"Failed to load config from {self._path}: {e}")
            return UserConfig()

    def save(self, config: UserConfig) -> None:
        """Save configuration to disk."""
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            data = {
                "areas": {
                    area_id: ac.model_dump()
                    for area_id, ac in config.areas.items()
                }
            }
            self._path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save config to {self._path}: {e}")
            raise