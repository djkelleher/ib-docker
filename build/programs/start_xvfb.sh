#!/bin/bash

log() {
	#local timestamp
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp  $1"
}

start_xvfb() {
	# Ensure X11 dir exists with correct ownership and perms early
	if [ ! -d /tmp/.X11-unix ]; then
		mkdir -p /tmp/.X11-unix
	fi
	# If root set ownership & perms; non-root skip to avoid errors
	if [ "$(id -u)" = "0" ]; then
		chown root:root /tmp/.X11-unix 2>/dev/null || true
		chmod 1777 /tmp/.X11-unix 2>/dev/null || true
	fi

	# Use DISPLAY environment variable or default to :1
	DISPLAY="${DISPLAY:-:1}"
	export DISPLAY

	log "Starting Xvfb server. Using display: $DISPLAY"
	display_no="${DISPLAY#:}"

	# More thorough cleanup of existing X server processes and files
	log "Cleaning up any existing X server processes and files..."

	# Kill any existing Xvfb processes completely (with retries)
	for _ in {1..3}; do
		pkill -9 -f "Xvfb.*${DISPLAY}" 2>/dev/null || true
		pkill -9 -f "Xvfb" 2>/dev/null || true
		sleep 1
	done

	# Remove all possible X server artifacts for this display
	rm -f "/tmp/.X${display_no}-lock" 2>/dev/null || true
	rm -f "/tmp/.X11-unix/X${display_no}" 2>/dev/null || true
	rm -f "/var/run/X${display_no}" 2>/dev/null || true
	rm -f "/var/lock/X${display_no}" 2>/dev/null || true

	# Additional cleanup - check for any lingering processes
	if pgrep -f "Xvfb.*${DISPLAY}" >/dev/null 2>&1; then
		log "Warning: Found lingering Xvfb processes, attempting forceful cleanup"
		pkill -KILL -f "Xvfb.*${DISPLAY}" 2>/dev/null || true
		sleep 2
	fi

	# Allow override of screen depth & size. Default to 1600x1200x24 for better color fidelity.
	VNC_SCREEN_DIMENSION="${VNC_SCREEN_DIMENSION:-1600x1200x24}"
	log "Starting virtual frame buffer. Display $DISPLAY. Screen dimension: $VNC_SCREEN_DIMENSION"

	# Create Xauth file for the user
	XAUTHORITY="$HOME/.Xauthority"
	export XAUTHORITY
	touch "$XAUTHORITY"
	chmod 600 "$XAUTHORITY"
	# Generate MIT-MAGIC-COOKIE-1
	xauth add "$DISPLAY" . "$(openssl rand -hex 16)" 2>/dev/null || true
	xauth add "localhost$DISPLAY" . "$(openssl rand -hex 16)" 2>/dev/null || true
	xauth add "$(hostname)$DISPLAY" . "$(openssl rand -hex 16)" 2>/dev/null || true

	# Small delay to ensure cleanup is complete
	sleep 3

	# Start Xvfb with additional options for stability
	log "Executing Xvfb with display $DISPLAY"
	exec /usr/bin/Xvfb "$DISPLAY" -ac -screen 0 "$VNC_SCREEN_DIMENSION" -noreset -nolisten tcp
}

start_xvfb
