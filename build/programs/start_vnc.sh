#!/bin/bash

source /usr/local/lib/ib_utils

start_vnc() {
	if [[ -z $VNC_PWD ]]; then
		log "VNC password is not set (VNC_PWD). Will not start VNC."
		exit 1
	fi
	log "Found VNC password (VNC_PWD)."
	wait_for_x_server
	# get display used by xvfb
	DISPLAY=$(cat /tmp/display_info)
	export DISPLAY
	# Set up X11 authentication if needed
	export XAUTHORITY="$HOME/.Xauthority"
	## start VNC server.
	# display: X11 server display to connect to.
	# forever: Keep listening for more connections rather than exiting as soon as the first client(s) disconnect.
	# shared: VNC display is shared, i.e. more than one viewer can connect at the same time.
	# noipv6: Do not try to use IPv6 for any listening or connecting sockets.
	# quiet: reduce verbose output
	# noxdamage: disable X DAMAGE extension warnings
	exec /usr/bin/x11vnc -ncache 10 -ncache_cr -passwd "$VNC_PWD" -display "$DISPLAY" -forever -shared -noipv6 -quiet -noxdamage
}

start_vnc
