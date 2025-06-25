#!/bin/bash

DISPLAY=${DISPLAY:-:0}
export DISPLAY

log() {
	#local timestamp
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp  $1"
}

start_xvfb() {
	echo "Starting Xvfb server"
	display_no=$(echo "$DISPLAY" | sed 's/^://')
	rm -f /tmp/.X${display_no}-lock
	rm -r /tmp/.X11-unix
	VNC_SCREEN_DIMENSION=${VNC_SCREEN_DIMENSION:-1280x1024x16}
	log "Starting virtual frame buffer. Display $DISPLAY. Screen dimension: $VNC_SCREEN_DIMENSION"
	## start virtual frame buffer.
	# creates screen screennum and sets its width, height, and depth to W, H, and D respectively. By default, only screen 0 exists and has the dimensions 1280x1024x8.
	/usr/bin/Xvfb $DISPLAY -ac -screen 0 $VNC_SCREEN_DIMENSION
}

start_xvfb
