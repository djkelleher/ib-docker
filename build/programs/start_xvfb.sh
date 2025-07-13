#!/bin/bash

DISPLAY=${DISPLAY:-:0}
export DISPLAY

log() {
	#local timestamp
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp  $1"
}

start_xvfb() {
	echo "Starting Xvfb server. Using display: $DISPLAY"
	display_no="${DISPLAY#:}"
	# Kill any existing Xvfb processes completely
	pkill -9 -f "Xvfb" 2>/dev/null || true
	sleep 1
	# Clean up any existing X11 locks and sockets
	rm -f "/tmp/.X${display_no}-lock" 2>/dev/null || true
	rm -f "/tmp/.X11-unix/X${display_no}" 2>/dev/null || true
	rm -rf /tmp/.X11-unix 2>/dev/null || true
	# Recreate X11 directory with proper ownership
	mkdir -p /tmp/.X11-unix 2>/dev/null || true
	chmod 1777 /tmp/.X11-unix 2>/dev/null || true
	# Set default screen dimension
	VNC_SCREEN_DIMENSION="${VNC_SCREEN_DIMENSION:-1600x1200x16}"
	log "Starting virtual frame buffer. Display $DISPLAY. Screen dimension: $VNC_SCREEN_DIMENSION"
	# Create Xauth file for the user
	XAUTHORITY="$HOME/.Xauthority"
	export XAUTHORITY
	touch "$XAUTHORITY"
	xauth add "$DISPLAY" . "$(openssl rand -hex 16)" 2>/dev/null || true
	# Save DISPLAY info for other services
	echo "$DISPLAY" >/tmp/display_info
	# Start virtual frame buffer with optimized flags
	# -ac: disable access control restrictions
	# -extension RANDR: disable RANDR extension (not needed in headless)
	# -extension RENDER: keep render extension for better graphics
	# -noreset: don't reset after last client exits
	# Set environment variables to reduce warnings
	export XKB_DEFAULT_RULES="base"
	export XKB_DEFAULT_MODEL="pc105"
	export XKB_DEFAULT_LAYOUT="us"
	exec /usr/bin/Xvfb "$DISPLAY" -ac -screen 0 "$VNC_SCREEN_DIMENSION" -noreset +extension RENDER -extension GLX 2>/dev/null
}

start_xvfb
