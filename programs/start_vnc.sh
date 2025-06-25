#!/bin/bash

DISPLAY=${DISPLAY:-:0}
export DISPLAY

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
	log "Starting VNC server. Display $DISPLAY"
	## start VNC server.
	# display: X11 server display to connect to.
	# forever: Keep listening for more connections rather than exiting as soon as the first client(s) disconnect.
	# shared: VNC display is shared, i.e. more than one viewer can connect at the same time.
	# noipv6: Do not try to use IPv6 for any listening or connecting sockets.
	# logappend: Write stderr messages to file logfile instead of to the terminal.
	/usr/bin/x11vnc -ncache 10 -ncache_cr -passwd $VNC_PWD -display $DISPLAY -forever -shared -noipv6
}

start_vnc
