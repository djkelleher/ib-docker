#!/bin/bash
# Socat port forwarding script

set -Eo pipefail

if [ -z "${API_PORT}" ] || [ -z "${SOCAT_PORT}" ]; then
	echo ".> API_PORT or SOCAT_PORT not set. API_PORT: ${API_PORT}, SOCAT_PORT: ${SOCAT_PORT}"
	exit 1
fi

echo ".> Starting socat port forwarding from 0.0.0.0:${SOCAT_PORT} to 127.0.0.1:${API_PORT}"

# Use socat to forward from all interfaces to localhost
# This allows external connections to reach the IB Gateway/TWS API
socat "TCP-LISTEN:${SOCAT_PORT},fork,reuseaddr" "TCP:127.0.0.1:${API_PORT}"
