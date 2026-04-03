from __future__ import annotations

from pydantic import BaseModel, Field


class Area(BaseModel):
    area_id: str
    name: str
    icon: str | None = None
    floor_id: str | None = None
    aliases: list[str] = Field(default_factory=list)


class DeviceEntry(BaseModel):
    id: str
    area_id: str | None = None
    name: str | None = None
    name_by_user: str | None = None
    disabled_by: str | None = None


class EntityEntry(BaseModel):
    entity_id: str
    unique_id: str = ""
    platform: str = ""
    area_id: str | None = None
    device_id: str | None = None
    disabled_by: str | None = None
    hidden_by: str | None = None
    original_name: str | None = None
    name: str | None = None
    entity_category: str | None = None


class ResolvedEntity(BaseModel):
    """Entity with its resolved area (from direct assignment or device inheritance)."""

    entity_id: str
    domain: str
    name: str
    area_id: str
    area_name: str
    source: str  # "direct" | "device"
    homekit_supported: bool
    disabled: bool
    hidden: bool
    entity_category: str | None = None


class AreaSummary(BaseModel):
    """Summary of an area for the area list view."""

    area_id: str
    name: str
    icon: str | None = None
    entity_count: int
    homekit_entity_count: int
    domain_counts: dict[str, int]


class AreaConfig(BaseModel):
    """User's configuration for one area."""

    area_id: str
    enabled: bool = False
    bridge_name: str = ""
    mode: str = "all_domains"  # "all_domains" | "selected_domains" | "manual"
    include_domains: list[str] = Field(default_factory=list)
    include_entities: list[str] = Field(default_factory=list)
    exclude_entities: list[str] = Field(default_factory=list)


class UserConfig(BaseModel):
    """Complete user configuration."""

    areas: dict[str, AreaConfig] = Field(default_factory=dict)


class BridgeConfig(BaseModel):
    """Generated configuration for one HomeKit bridge."""

    name: str
    port: int
    mode: str = "bridge"
    filter: dict


class GenerationResult(BaseModel):
    yaml_content: str
    bridges: list[BridgeConfig]
    warnings: list[str]
    entity_count_per_bridge: dict[str, int]
