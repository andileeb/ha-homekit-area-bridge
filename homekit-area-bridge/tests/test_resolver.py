from app.resolver import build_area_summaries, resolve_from_raw


class TestResolveFromRaw:
    def test_direct_area_assignment(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        kitchen_entities = area_entities.get("kitchen", [])
        entity_ids = [e.entity_id for e in kitchen_entities]
        assert "light.kitchen_ceiling" in entity_ids
        # Check source is "direct"
        ceiling = next(e for e in kitchen_entities if e.entity_id == "light.kitchen_ceiling")
        assert ceiling.source == "direct"

    def test_device_inherited_area(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        kitchen_entities = area_entities.get("kitchen", [])
        entity_ids = [e.entity_id for e in kitchen_entities]
        assert "switch.kitchen_coffee" in entity_ids
        coffee = next(e for e in kitchen_entities if e.entity_id == "switch.kitchen_coffee")
        assert coffee.source == "device"

    def test_unassigned_entities_skipped(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        all_entity_ids = [
            e.entity_id for entities in area_entities.values() for e in entities
        ]
        assert "light.floating_light" not in all_entity_ids
        assert "light.orphan" not in all_entity_ids

    def test_all_areas_returned(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        area_ids = {a.area_id for a in areas}
        assert area_ids == {"kitchen", "living_room", "bedroom", "empty_room"}

    def test_empty_area_has_no_entities(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        assert "empty_room" not in area_entities

    def test_disabled_entity_marked(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        bedroom = area_entities.get("bedroom", [])
        disabled = next(e for e in bedroom if e.entity_id == "light.bedroom_disabled")
        assert disabled.disabled is True

    def test_hidden_entity_marked(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        bedroom = area_entities.get("bedroom", [])
        hidden = next(e for e in bedroom if e.entity_id == "switch.bedroom_hidden")
        assert hidden.hidden is True

    def test_diagnostic_entity_category_preserved(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        kitchen = area_entities.get("kitchen", [])
        diag = next(e for e in kitchen if e.entity_id == "sensor.kitchen_hub_signal")
        assert diag.entity_category == "diagnostic"

    def test_homekit_supported_flag(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        kitchen = area_entities.get("kitchen", [])
        light = next(e for e in kitchen if e.entity_id == "light.kitchen_ceiling")
        assert light.homekit_supported is True
        firmware = next(e for e in kitchen if e.entity_id == "update.kitchen_hub_firmware")
        assert firmware.homekit_supported is False

    def test_domain_extraction(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        kitchen = area_entities.get("kitchen", [])
        coffee = next(e for e in kitchen if e.entity_id == "switch.kitchen_coffee")
        assert coffee.domain == "switch"

    def test_name_resolution(self, sample_areas, sample_devices, sample_entities):
        """Uses 'name' if set, otherwise falls back to 'original_name'."""
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        living = area_entities.get("living_room", [])
        main_light = next(e for e in living if e.entity_id == "light.living_room_main")
        assert main_light.name == "Living Room Main"  # has explicit name
        coffee = next(
            e for e in area_entities["kitchen"] if e.entity_id == "switch.kitchen_coffee"
        )
        assert coffee.name == "Coffee Machine"  # falls back to original_name

    def test_direct_area_overrides_device_area(self, sample_areas, sample_devices, sample_entities):
        """If entity has direct area_id, that wins over device's area."""
        # Add an entity with both direct area and a device in a different area
        entities = sample_entities + [{
            "entity_id": "light.override_test",
            "unique_id": "override1",
            "platform": "test",
            "area_id": "bedroom",
            "device_id": "dev_kitchen_hub",  # device is in kitchen
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Override Test",
            "name": None,
            "entity_category": None,
        }]
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, entities)
        bedroom = area_entities.get("bedroom", [])
        override = next(e for e in bedroom if e.entity_id == "light.override_test")
        assert override.area_id == "bedroom"
        assert override.source == "direct"


class TestBuildAreaSummaries:
    def test_summaries_sorted_by_name(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        summaries = build_area_summaries(areas, area_entities)
        names = [s.name for s in summaries]
        assert names == sorted(names)

    def test_entity_count_excludes_disabled_hidden_diagnostic(
        self, sample_areas, sample_devices, sample_entities
    ):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        summaries = build_area_summaries(areas, area_entities)
        kitchen = next(s for s in summaries if s.area_id == "kitchen")
        # kitchen has: ceiling (light), coffee (switch), temperature (sensor),
        # hub_signal (diagnostic - excluded), firmware (update - visible but not homekit)
        assert kitchen.entity_count == 4  # ceiling, coffee, temp, firmware (not diagnostic)
        assert kitchen.homekit_entity_count == 3  # ceiling, coffee, temp (not firmware)

    def test_domain_counts(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        summaries = build_area_summaries(areas, area_entities)
        kitchen = next(s for s in summaries if s.area_id == "kitchen")
        assert kitchen.domain_counts == {"light": 1, "switch": 1, "sensor": 1}

    def test_empty_area_summary(self, sample_areas, sample_devices, sample_entities):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        summaries = build_area_summaries(areas, area_entities)
        empty = next(s for s in summaries if s.area_id == "empty_room")
        assert empty.entity_count == 0
        assert empty.homekit_entity_count == 0
        assert empty.domain_counts == {}

    def test_bedroom_counts_exclude_disabled_and_hidden(
        self, sample_areas, sample_devices, sample_entities
    ):
        areas, area_entities = resolve_from_raw(sample_areas, sample_devices, sample_entities)
        summaries = build_area_summaries(areas, area_entities)
        bedroom = next(s for s in summaries if s.area_id == "bedroom")
        # bedroom has: disabled light (excluded), hidden switch (excluded), lamp (visible)
        assert bedroom.entity_count == 1
        assert bedroom.homekit_entity_count == 1
