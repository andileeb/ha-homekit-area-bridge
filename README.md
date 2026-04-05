# HomeKit Area Bridge

A Home Assistant app that automatically generates one HomeKit bridge per area (room), with a web UI for configuring entity inclusion/exclusion and domain filtering.

## What it does

1. Reads areas, devices, and entities from Home Assistant
2. Groups entities by area (via direct assignment or device inheritance)
3. Provides a UI to enable/disable areas, filter by domain, include/exclude entities
4. Generates HomeKit YAML configuration with one bridge per enabled area
5. Writes config to `/config/packages/homekit_area_bridge.yaml`

## Installation

### As a Home Assistant App

1. Add this repository to your Home Assistant app store:
   - Go to **Settings > Apps > App Store**
   - Click the three-dot menu > **Repositories**
   - Add: `https://github.com/andileeb/ha-homekit-area-bridge`

2. Install the **HomeKit Area Bridge** app

3. Ensure your `configuration.yaml` includes packages:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

4. Start the app and open the Web UI from the sidebar

## Usage

1. Open the HomeKit Area Bridge UI from the Home Assistant sidebar
2. You'll see all your areas with entity counts
3. Enable the areas you want as HomeKit bridges
4. Configure each area:
   - **All Supported**: Includes all HomeKit-compatible entities in the area
   - **Select Domains**: Choose which domains (light, switch, sensor, etc.) to include
   - **Manual**: Pick individual entities
5. Optionally exclude specific entities
6. Click **Preview YAML** to see the generated configuration
7. Click **Write to Config** to save
8. Restart Home Assistant to apply

## Tip: Set up rooms in Apple Home first

When you add a HomeKit bridge to Apple Home, all its entities are placed in the same room. To take advantage of this:

1. Enable an area bridge **even if it has no entities yet** — empty bridges are allowed
2. Write the config and restart Home Assistant
3. Pair the bridge in the Apple Home app and assign it to the matching room
4. Then go back to the app UI and add entities to the bridge
5. After restarting HA, all new entities will automatically appear in the correct Apple Home room

This avoids having to manually move dozens of entities between rooms in Apple Home.

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `log_level` | `info` | Logging level (debug, info, warning, error) |
| `homekit_start_port` | `21100` | Base port for HomeKit bridges (each bridge gets a sequential port) |

## How it works

- Uses the Home Assistant WebSocket API to fetch area, device, and entity registries
- Entities inherit their area from their parent device if not directly assigned
- Always uses `include_entities` (not `include_domains`) because HomeKit's domain filter is global, not per-bridge
- Disabled, hidden, and diagnostic entities are automatically excluded
- Bridge names are limited to 25 characters and must be unique

## Supported domains

alarm_control_panel, automation, binary_sensor, camera, climate, cover, device_tracker, fan, humidifier, input_boolean, input_button, input_select, light, lock, media_player, person, remote, scene, script, select, sensor, switch, vacuum, valve, water_heater

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

## License

MIT
