# Changelog

## 0.1.3

- Refactor to app factory pattern for testability
- Add build deps (gcc, musl-dev) to Dockerfile for aiohttp C extensions on Alpine
- Relax version pins to allow compatible versions
- Add 21 route tests covering all API endpoints, ingress, and static files
- Make ConfigStore path injectable

## 0.1.2

- Fix "Not Found" on UI load: move static file mount after route registration
- Add explicit WORKDIR in Dockerfile for reliable module resolution
- Add graceful error handling when frontend files are missing

## 0.1.1

- Fix s6-overlay startup error (`init: false` to prevent tini from stealing PID 1)
- Restructure repo for HA app store discovery (subdirectory + repository.yaml)
- Update terminology from "add-on" to "app"
- Add multi-arch build.yaml
- Use simplified config map syntax

## 0.1.0

- Initial release
- Fetch areas, devices, and entities from Home Assistant via WebSocket API
- Group entities by area (direct assignment and device inheritance)
- Web UI with area enable/disable, domain filtering, and per-entity include/exclude
- Three selection modes: All Supported, Select Domains, Manual
- YAML preview before writing
- Generate HomeKit bridge config to `/config/packages/homekit_area_bridge.yaml`
- Persistent user configuration across restarts
- Automatic filtering of disabled, hidden, and diagnostic entities
- Bridge name uniqueness enforcement and 150-entity limit warnings
