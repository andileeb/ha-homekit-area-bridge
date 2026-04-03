import yaml

from app.generator import (
    HOMEKIT_ENTITY_LIMIT,
    MAX_BRIDGE_NAME_LENGTH,
    _unique_name,
    generate_homekit_yaml,
)
from app.models import AreaConfig, ResolvedEntity


def _make_entity(
    entity_id: str,
    domain: str | None = None,
    area_id: str = "kitchen",
    homekit_supported: bool = True,
    disabled: bool = False,
    hidden: bool = False,
    entity_category: str | None = None,
) -> ResolvedEntity:
    if domain is None:
        domain = entity_id.split(".")[0]
    return ResolvedEntity(
        entity_id=entity_id,
        domain=domain,
        name=entity_id.replace(".", " ").replace("_", " ").title(),
        area_id=area_id,
        area_name="Kitchen",
        source="direct",
        homekit_supported=homekit_supported,
        disabled=disabled,
        hidden=hidden,
        entity_category=entity_category,
    )


class TestGenerateHomekitYaml:
    def test_single_area_all_domains(self):
        entities = {
            "kitchen": [
                _make_entity("light.kitchen_ceiling"),
                _make_entity("switch.kitchen_coffee"),
            ]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
                mode="all_domains",
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        assert len(result.bridges) == 1
        assert result.bridges[0].name == "Kitchen Bridge"
        assert result.bridges[0].port == 21100
        assert "light.kitchen_ceiling" in result.bridges[0].filter["include_entities"]
        assert "switch.kitchen_coffee" in result.bridges[0].filter["include_entities"]

    def test_selected_domains_filtering(self):
        entities = {
            "kitchen": [
                _make_entity("light.kitchen_ceiling"),
                _make_entity("switch.kitchen_coffee"),
                _make_entity("sensor.kitchen_temp"),
            ]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
                mode="selected_domains",
                include_domains=["light", "switch"],
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        assert len(result.bridges) == 1
        included = result.bridges[0].filter["include_entities"]
        assert "light.kitchen_ceiling" in included
        assert "switch.kitchen_coffee" in included
        assert "sensor.kitchen_temp" not in included

    def test_manual_entity_selection(self):
        entities = {
            "kitchen": [
                _make_entity("light.kitchen_ceiling"),
                _make_entity("switch.kitchen_coffee"),
            ]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
                mode="manual",
                include_entities=["light.kitchen_ceiling"],
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        included = result.bridges[0].filter["include_entities"]
        assert included == ["light.kitchen_ceiling"]

    def test_exclude_entities(self):
        entities = {
            "kitchen": [
                _make_entity("light.kitchen_ceiling"),
                _make_entity("switch.kitchen_coffee"),
            ]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
                mode="all_domains",
                exclude_entities=["switch.kitchen_coffee"],
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        included = result.bridges[0].filter["include_entities"]
        assert "light.kitchen_ceiling" in included
        assert "switch.kitchen_coffee" not in included

    def test_disabled_area_skipped(self):
        entities = {
            "kitchen": [_make_entity("light.kitchen_ceiling")]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=False,
                bridge_name="Kitchen Bridge",
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        assert len(result.bridges) == 0

    def test_empty_area_skipped(self):
        entities = {"kitchen": []}
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        assert len(result.bridges) == 0

    def test_disabled_entities_filtered_out(self):
        entities = {
            "kitchen": [
                _make_entity("light.kitchen_ceiling"),
                _make_entity("light.disabled", disabled=True),
            ]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
                mode="all_domains",
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        included = result.bridges[0].filter["include_entities"]
        assert "light.disabled" not in included

    def test_hidden_entities_filtered_out(self):
        entities = {
            "kitchen": [
                _make_entity("light.kitchen_ceiling"),
                _make_entity("light.hidden", hidden=True),
            ]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
                mode="all_domains",
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        included = result.bridges[0].filter["include_entities"]
        assert "light.hidden" not in included

    def test_diagnostic_entities_filtered_out(self):
        entities = {
            "kitchen": [
                _make_entity("light.kitchen_ceiling"),
                _make_entity("sensor.diag", entity_category="diagnostic"),
            ]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
                mode="all_domains",
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        included = result.bridges[0].filter["include_entities"]
        assert "sensor.diag" not in included

    def test_non_homekit_entities_filtered_out(self):
        entities = {
            "kitchen": [
                _make_entity("light.kitchen_ceiling"),
                _make_entity("update.firmware", homekit_supported=False),
            ]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
                mode="all_domains",
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        included = result.bridges[0].filter["include_entities"]
        assert "update.firmware" not in included

    def test_multi_area_port_sequencing(self):
        entities = {
            "kitchen": [_make_entity("light.k1", area_id="kitchen")],
            "bedroom": [_make_entity("light.b1", area_id="bedroom")],
        }
        configs = [
            AreaConfig(area_id="kitchen", enabled=True, bridge_name="Kitchen"),
            AreaConfig(area_id="bedroom", enabled=True, bridge_name="Bedroom"),
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        assert len(result.bridges) == 2
        assert result.bridges[0].port == 21100
        assert result.bridges[1].port == 21101

    def test_entity_limit_warning(self):
        entities = {
            "kitchen": [
                _make_entity(f"light.kitchen_{i}") for i in range(160)
            ]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
                mode="all_domains",
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        assert len(result.warnings) == 1
        assert "150" in result.warnings[0]

    def test_yaml_output_is_valid(self):
        entities = {
            "kitchen": [
                _make_entity("light.kitchen_ceiling"),
                _make_entity("switch.kitchen_coffee"),
            ]
        }
        configs = [
            AreaConfig(
                area_id="kitchen",
                enabled=True,
                bridge_name="Kitchen Bridge",
                mode="all_domains",
            )
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        # Should parse as valid YAML
        parsed = yaml.safe_load(result.yaml_content)
        assert "homekit" in parsed
        assert len(parsed["homekit"]) == 1
        assert parsed["homekit"][0]["name"] == "Kitchen Bridge"

    def test_yaml_has_header_comment(self):
        entities = {"kitchen": [_make_entity("light.k1")]}
        configs = [AreaConfig(area_id="kitchen", enabled=True, bridge_name="Kitchen")]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        assert result.yaml_content.startswith("# Auto-generated by HomeKit Area Bridge")

    def test_empty_config_produces_no_bridges_yaml(self):
        result = generate_homekit_yaml([], {}, start_port=21100)
        assert "No bridges configured" in result.yaml_content

    def test_entity_count_per_bridge(self):
        entities = {
            "kitchen": [
                _make_entity("light.k1"),
                _make_entity("switch.k2"),
            ]
        }
        configs = [
            AreaConfig(area_id="kitchen", enabled=True, bridge_name="Kitchen")
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        assert result.entity_count_per_bridge["Kitchen"] == 2

    def test_entities_sorted_in_output(self):
        entities = {
            "kitchen": [
                _make_entity("switch.z_switch"),
                _make_entity("light.a_light"),
            ]
        }
        configs = [
            AreaConfig(area_id="kitchen", enabled=True, bridge_name="Kitchen")
        ]
        result = generate_homekit_yaml(configs, entities, start_port=21100)
        included = result.bridges[0].filter["include_entities"]
        assert included == sorted(included)


class TestUniqueName:
    def test_unique_name_no_collision(self):
        assert _unique_name("Kitchen Bridge", set()) == "Kitchen Bridge"

    def test_unique_name_with_collision(self):
        used = {"Kitchen Bridge"}
        assert _unique_name("Kitchen Bridge", used) == "Kitchen Bridge 2"

    def test_unique_name_multiple_collisions(self):
        used = {"Kitchen Bridge", "Kitchen Bridge 2"}
        assert _unique_name("Kitchen Bridge", used) == "Kitchen Bridge 3"

    def test_unique_name_truncation(self):
        long_name = "A" * 30
        result = _unique_name(long_name, set())
        assert len(result) <= MAX_BRIDGE_NAME_LENGTH

    def test_unique_name_empty_becomes_bridge(self):
        assert _unique_name("", set()) == "Bridge"

    def test_unique_name_strips_invalid_chars(self):
        result = _unique_name("Kitchen!@#$%Bridge", set())
        assert result == "KitchenBridge"
