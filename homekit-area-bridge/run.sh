#!/usr/bin/with-contenv bashio

# Extract app options
export LOG_LEVEL=$(bashio::config 'log_level')
export HOMEKIT_START_PORT=$(bashio::config 'homekit_start_port')

bashio::log.info "Starting HomeKit Area Bridge..."
bashio::log.info "Log level: ${LOG_LEVEL}"
bashio::log.info "HomeKit start port: ${HOMEKIT_START_PORT}"

exec python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8099 \
    --log-level "${LOG_LEVEL}"
