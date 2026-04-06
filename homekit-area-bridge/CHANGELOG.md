# Changelog

## 0.2.0

- Add "Show Diff" button to compare generated YAML against current on-disk config before applying
- Color-coded diff overlay: green for additions, red for removals, with unified diff format
- `/api/generate` now returns `diff`, `has_changes`, and `current_yaml` fields

## 0.1.9

- Minimal Config now prefers physical devices (lights, switches, covers, climate, etc.) and skips automations, scripts, scenes, helpers, persons, and device trackers

## 0.1.8

- Dynamic Enable All / Disable All label syncs with individual area toggles
- Add confirmation dialog before applying Minimal Config to prevent accidental overwrite
- Add cache-busting version query param to static assets to prevent stale JS/CSS after updates

## 0.1.7

- Add "Enable All / Disable All" bulk toggle button
- Add "Minimal Config" button: enables all areas with 1 entity each for quick HomeKit room setup

## 0.1.6

- Add "automatic room placement" workflow tip to README: start with one entity per bridge, pair in Apple Home, then add the rest

## 0.1.5

- Add post-apply result overlay with bridge details (name, port, entity count) and pairing instructions
- Detect missing `packages:` directive in `configuration.yaml` and warn user with fix snippet
- Enrich `/api/apply` and `/api/status` responses with bridge details and `packages_configured` flag

## 0.1.4

- Fix 404 on UI load: HA ingress proxy sends `//` (double slash) as the request path; add ASGI middleware to normalize `//` → `/` before routing

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
