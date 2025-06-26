#!/bin/bash
# Socat startup script for supervisord

set -Eo pipefail

# Source SSH utilities for port configuration
source /usr/local/lib/ssh_utils

# Set up ports
set_ports

# Check if we should start socat based on SSH_TUNNEL mode and ENABLE_SOCAT setting
if [ "$SSH_TUNNEL" = "yes" ]; then
	echo ".> SSH tunnel only mode, socat disabled"
	# Keep the service running but don't do anything
	while true; do sleep 30; done
elif [ "$ENABLE_SOCAT" = "no" ]; then
	echo ".> Socat explicitly disabled via ENABLE_SOCAT=no"
	echo ".> With host networking, you can connect directly to localhost:${API_PORT}"
	# Keep the service running but don't do anything
	while true; do sleep 30; done
elif [ "$SSH_TUNNEL" = "both" ]; then
	echo ".> Both SSH tunnel and socat mode, starting socat"
else
	echo ".> Standard mode, starting socat for external access"
	echo ".> Forwarding 0.0.0.0:${SOCAT_PORT} -> 127.0.0.1:${API_PORT}"
fi

# Start socat port forwarding
exec /usr/local/bin/run_socat
