import pytest


@pytest.fixture
def sample_areas():
    return [
        {"area_id": "kitchen", "name": "Kitchen", "icon": "mdi:silverware-fork-knife", "floor_id": None, "aliases": []},
        {"area_id": "living_room", "name": "Living Room", "icon": "mdi:sofa", "floor_id": None, "aliases": []},
        {"area_id": "bedroom", "name": "Bedroom", "icon": "mdi:bed", "floor_id": None, "aliases": []},
        {"area_id": "empty_room", "name": "Empty Room", "icon": None, "floor_id": None, "aliases": []},
    ]


@pytest.fixture
def sample_devices():
    return [
        {"id": "dev_kitchen_hub", "area_id": "kitchen", "name": "Kitchen Hub", "name_by_user": None, "disabled_by": None},
        {"id": "dev_living_tv", "area_id": "living_room", "name": "Living Room TV", "name_by_user": None, "disabled_by": None},
        {"id": "dev_no_area", "area_id": None, "name": "Floating Device", "name_by_user": None, "disabled_by": None},
        {"id": "dev_bedroom_lamp", "area_id": "bedroom", "name": "Bedroom Lamp", "name_by_user": None, "disabled_by": None},
    ]


@pytest.fixture
def sample_entities():
    return [
        # Kitchen - direct area assignment
        {
            "entity_id": "light.kitchen_ceiling",
            "unique_id": "abc1",
            "platform": "hue",
            "area_id": "kitchen",
            "device_id": None,
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Kitchen Ceiling",
            "name": None,
            "entity_category": None,
        },
        # Kitchen - area via device
        {
            "entity_id": "switch.kitchen_coffee",
            "unique_id": "abc2",
            "platform": "shelly",
            "area_id": None,
            "device_id": "dev_kitchen_hub",
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Coffee Machine",
            "name": None,
            "entity_category": None,
        },
        # Kitchen - sensor via device
        {
            "entity_id": "sensor.kitchen_temperature",
            "unique_id": "abc3",
            "platform": "shelly",
            "area_id": None,
            "device_id": "dev_kitchen_hub",
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Kitchen Temperature",
            "name": None,
            "entity_category": None,
        },
        # Kitchen - diagnostic entity (should be filtered in summaries)
        {
            "entity_id": "sensor.kitchen_hub_signal",
            "unique_id": "abc3b",
            "platform": "shelly",
            "area_id": None,
            "device_id": "dev_kitchen_hub",
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Signal Strength",
            "name": None,
            "entity_category": "diagnostic",
        },
        # Living Room - direct area
        {
            "entity_id": "light.living_room_main",
            "unique_id": "abc4",
            "platform": "hue",
            "area_id": "living_room",
            "device_id": None,
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Main Light",
            "name": "Living Room Main",
            "entity_category": None,
        },
        # Living Room - media_player via device
        {
            "entity_id": "media_player.living_room_tv",
            "unique_id": "abc5",
            "platform": "cast",
            "area_id": None,
            "device_id": "dev_living_tv",
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Living Room TV",
            "name": None,
            "entity_category": None,
        },
        # Entity with no area and no device area -> should be skipped
        {
            "entity_id": "light.floating_light",
            "unique_id": "abc6",
            "platform": "hue",
            "area_id": None,
            "device_id": "dev_no_area",
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Floating Light",
            "name": None,
            "entity_category": None,
        },
        # Entity with no area and no device -> should be skipped
        {
            "entity_id": "light.orphan",
            "unique_id": "abc7",
            "platform": "hue",
            "area_id": None,
            "device_id": None,
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Orphan Light",
            "name": None,
            "entity_category": None,
        },
        # Disabled entity in bedroom
        {
            "entity_id": "light.bedroom_disabled",
            "unique_id": "abc8",
            "platform": "hue",
            "area_id": "bedroom",
            "device_id": None,
            "disabled_by": "user",
            "hidden_by": None,
            "original_name": "Disabled Light",
            "name": None,
            "entity_category": None,
        },
        # Hidden entity in bedroom
        {
            "entity_id": "switch.bedroom_hidden",
            "unique_id": "abc9",
            "platform": "shelly",
            "area_id": "bedroom",
            "device_id": None,
            "disabled_by": None,
            "hidden_by": "user",
            "original_name": "Hidden Switch",
            "name": None,
            "entity_category": None,
        },
        # Normal bedroom entity via device
        {
            "entity_id": "light.bedroom_lamp",
            "unique_id": "abc10",
            "platform": "hue",
            "area_id": None,
            "device_id": "dev_bedroom_lamp",
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Bedroom Lamp",
            "name": None,
            "entity_category": None,
        },
        # Unsupported domain in kitchen (direct area)
        {
            "entity_id": "update.kitchen_hub_firmware",
            "unique_id": "abc11",
            "platform": "shelly",
            "area_id": "kitchen",
            "device_id": None,
            "disabled_by": None,
            "hidden_by": None,
            "original_name": "Firmware Update",
            "name": None,
            "entity_category": None,
        },
    ]
