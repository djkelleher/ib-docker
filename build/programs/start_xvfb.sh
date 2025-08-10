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

	echo "Starting Xvfb server. Using display: $DISPLAY"
	display_no="${DISPLAY#:}"
	# Kill any existing Xvfb processes completely
	pkill -9 -f "Xvfb" 2>/dev/null || true
	sleep 1
	# Only remove stale lock/socket for this display
	rm -f "/tmp/.X${display_no}-lock" 2>/dev/null || true
	rm -f "/tmp/.X11-unix/X${display_no}" 2>/dev/null || true

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
	sleep 2
	exec /usr/bin/Xvfb "$DISPLAY" -ac -screen 0 "$VNC_SCREEN_DIMENSION" -noreset
}

start_xvfb
