#!/bin/bash
set -euo pipefail

# Container entrypoint script to handle initialization and cleanup

source /usr/local/lib/ib_utils

log() {
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp [ENTRYPOINT] $1"
}

cleanup_x_server() {
	local display_no
	local xvfb_pattern
	local x11vnc_pattern

	log "Performing initial X server cleanup..."
	display_no="$(x_display_number "$DISPLAY")"
	xvfb_pattern="$(x_display_process_pattern Xvfb "$DISPLAY")"
	x11vnc_pattern="$(x_display_process_pattern x11vnc "$DISPLAY")"

	# Kill any existing X server processes
	pkill -9 -f "$xvfb_pattern" 2>/dev/null || true
	pkill -9 -f "$x11vnc_pattern" 2>/dev/null || true

	# Clean up X server files and locks
	rm -f "/tmp/.X${display_no}-lock" 2>/dev/null || true
	rm -f "/tmp/.X11-unix/X${display_no}" 2>/dev/null || true
	rm -f "/var/run/X${display_no}" 2>/dev/null || true
	rm -f "/var/lock/X${display_no}" 2>/dev/null || true

	# Recreate X11 directory with correct permissions
	mkdir -p /tmp/.X11-unix
	if [ "$(id -u)" = "0" ]; then
		chown root:root /tmp/.X11-unix 2>/dev/null || true
		chmod 1777 /tmp/.X11-unix 2>/dev/null || true
	fi

	log "X server cleanup completed"
}

# Use DISPLAY environment variable or default to :1
DISPLAY="$(x_server_display "${DISPLAY:-:1}")"
export DISPLAY

# Perform initial cleanup
cleanup_x_server

log "Initializing runtime configuration"
init_container_settings

log "Starting supervisord with DISPLAY=$DISPLAY"

# Execute the original command (supervisord)
exec "$@"
