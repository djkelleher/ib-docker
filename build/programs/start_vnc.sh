#!/bin/bash

# Get DISPLAY from environment or wait for it to be set by xvfb
DISPLAY=${DISPLAY:-:0}

log() {
	#local timestamp
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp  $1"
}

start_vnc() {
	if [[ -z $VNC_PWD ]]; then
		log "VNC password is not set (VNC_PWD). Will not start VNC."
		return
	else
		log "Found VNC password (VNC_PWD)."
	fi
	
	# Wait for DISPLAY to be available from xvfb service
	timeout=30
	while [ $timeout -gt 0 ]; do
		# Check if we can read the DISPLAY from a shared location
		if [ -f "/tmp/display_info" ]; then
			DISPLAY=$(cat /tmp/display_info)
			export DISPLAY
			log "Found DISPLAY from xvfb: $DISPLAY"
			break
		fi
		sleep 1
		timeout=$((timeout - 1))
	done
	
	log "Starting VNC server. Display $DISPLAY"
	
	# Wait for X server to be ready - more robust check
	timeout=30
	while [ $timeout -gt 0 ]; do
		if DISPLAY=$DISPLAY xset q >/dev/null 2>&1; then
			log "X server is ready"
			break
		fi
		log "Waiting for X server to start... ($timeout seconds remaining)"
		sleep 1
		timeout=$((timeout - 1))
	done
	
	if [ $timeout -eq 0 ]; then
		log "ERROR: X server failed to start within 30 seconds"
		exit 1
	fi
	
	# Set up X11 authentication if needed
	export XAUTHORITY=$HOME/.Xauthority
	
	## start VNC server.
	# display: X11 server display to connect to.
	# forever: Keep listening for more connections rather than exiting as soon as the first client(s) disconnect.
	# shared: VNC display is shared, i.e. more than one viewer can connect at the same time.
	# noipv6: Do not try to use IPv6 for any listening or connecting sockets.
	# quiet: reduce verbose output
	# noxdamage: disable X DAMAGE extension warnings
	exec /usr/bin/x11vnc -ncache 10 -ncache_cr -passwd $VNC_PWD -display $DISPLAY -forever -shared -noipv6 -quiet -noxdamage
}

start_vnc
