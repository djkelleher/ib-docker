#!/bin/bash

# Container entrypoint script to handle initialization and cleanup

log() {
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp [ENTRYPOINT] $1"
}

cleanup_x_server() {
	log "Performing initial X server cleanup..."

	# Kill any existing X server processes
	pkill -9 -f "Xvfb" 2>/dev/null || true
	pkill -9 -f "x11vnc" 2>/dev/null || true

	# Clean up X server files and locks
	rm -rf /tmp/.X*-lock 2>/dev/null || true
	rm -rf /tmp/.X11-unix/* 2>/dev/null || true
	rm -rf /var/run/X* 2>/dev/null || true
	rm -rf /var/lock/X* 2>/dev/null || true

	# Recreate X11 directory with correct permissions
	mkdir -p /tmp/.X11-unix
	chmod 1777 /tmp/.X11-unix

	log "X server cleanup completed"
}

# Perform initial cleanup
cleanup_x_server

# Use DISPLAY environment variable or default to :1
DISPLAY="${DISPLAY:-:1}"
export DISPLAY

log "Starting supervisord with DISPLAY=$DISPLAY"

# Execute the original command (supervisord)
exec "$@"
