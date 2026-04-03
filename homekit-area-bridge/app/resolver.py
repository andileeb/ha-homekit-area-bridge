from __future__ import annotations

from collections import defaultdict

from app.ha_client import HAClient
from app.models import Area, AreaSummary, ResolvedEntity

# Domains supported by the HomeKit integration
HOMEKIT_SUPPORTED_DOMAINS = frozenset({
    "alarm_control_panel",
    "automation",
    "binary_sensor",
    "camera",
    "climate",
    "cover",
    "device_tracker",
    "fan",
    "humidifier",
    "input_boolean",
    "input_button",
    "input_select",
    "light",
    "lock",
    "media_player",
    "person",
    "remote",
    "scene",
    "script",
    "select",
    "sensor",
    "switch",
    "vacuum",
    "valve",
    "water_heater",
})


async def resolve_entities(
    client: HAClient,
) -> tuple[list[Area], dict[str, list[ResolvedEntity]]]:
    """
    Fetch areas, devices, and entities from HA, then resolve each entity
    to its area (direct assignment or device inheritance).

    Returns:
        - List of Area objects
        - Dict mapping area_id -> list of ResolvedEntity
          (only includes entities that have an area)
    """
    areas_raw, devices_raw, entities_raw = await client.fetch_all()
    return resolve_from_raw(areas_raw, devices_raw, entities_raw)


def resolve_from_raw(
    areas_raw: list[dict],
    devices_raw: list[dict],
    entities_raw: list[dict],
) -> tuple[list[Area], dict[str, list[ResolvedEntity]]]:
    """
    Pure function for entity resolution from raw registry data.
    Separated from async fetch for testability.
    """
    # Build lookups
    device_area_map: dict[str, str | None] = {
        d["id"]: d.get("area_id") for d in devices_raw
    }
    area_map: dict[str, Area] = {}
    for a in areas_raw:
        area = Area(
            area_id=a["area_id"],
            name=a["name"],
            icon=a.get("icon"),
            floor_id=a.get("floor_id"),
            aliases=a.get("aliases", []),
        )
        area_map[a["area_id"]] = area

    # Resolve each entity to its area
    area_entities: dict[str, list[ResolvedEntity]] = defaultdict(list)

    for ent in entities_raw:
        entity_id = ent.get("entity_id", "")
        if not entity_id or "." not in entity_id:
            continue

        domain = entity_id.split(".")[0]

        # Resolve area: direct > device > skip
        resolved_area_id = ent.get("area_id")
        source = "direct" if resolved_area_id else None

        if not resolved_area_id and ent.get("device_id"):
            resolved_area_id = device_area_map.get(ent["device_id"])
            if resolved_area_id:
                source = "device"

        # Skip entities without an area
        if not resolved_area_id or resolved_area_id not in area_map:
            continue

        area = area_map[resolved_area_id]
        name = ent.get("name") or ent.get("original_name") or entity_id

        area_entities[resolved_area_id].append(
            ResolvedEntity(
                entity_id=entity_id,
                domain=domain,
                name=name,
                area_id=resolved_area_id,
                area_name=area.name,
                source=source,  # type: ignore[arg-type]
                homekit_supported=domain in HOMEKIT_SUPPORTED_DOMAINS,
                disabled=ent.get("disabled_by") is not None,
                hidden=ent.get("hidden_by") is not None,
                entity_category=ent.get("entity_category"),
            )
        )

    return list(area_map.values()), dict(area_entities)


def build_area_summaries(
    areas: list[Area],
    area_entities: dict[str, list[ResolvedEntity]],
) -> list[AreaSummary]:
    """Build summary objects for the area list view."""
    summaries = []
    for area in areas:
        entities = area_entities.get(area.area_id, [])
        # Only count non-disabled, non-hidden, non-diagnostic entities
        visible = [
            e for e in entities
            if not e.disabled and not e.hidden and e.entity_category is None
        ]
        homekit = [e for e in visible if e.homekit_supported]

        domain_counts: dict[str, int] = {}
        for e in visible:
            if e.homekit_supported:
                domain_counts[e.domain] = domain_counts.get(e.domain, 0) + 1

        summaries.append(
            AreaSummary(
                area_id=area.area_id,
                name=area.name,
                icon=area.icon,
                entity_count=len(visible),
                homekit_entity_count=len(homekit),
                domain_counts=domain_counts,
            )
        )

    # Sort by name
    summaries.sort(key=lambda s: s.name)
    return summaries
