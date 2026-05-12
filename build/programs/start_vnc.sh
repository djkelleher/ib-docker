#!/bin/bash
set -euo pipefail

source /usr/local/lib/ib_utils

start_vnc() {
	local vnc_password_file
	local vnc_listen_port

	if [[ -z ${VNC_PWD:-} ]]; then
		log "VNC password is not set (VNC_PWD). VNC is disabled."
		exec sleep infinity
	fi
	log "Found VNC password (VNC_PWD). Starting VNC."
	vnc_listen_port="$(vnc_port)"
	wait_for_x_server
	# Set up X11 authentication if needed
	export XAUTHORITY="$HOME/.Xauthority"
	## start VNC server.
	# display: X11 server display to connect to.
	# forever: Keep listening for more connections rather than exiting as soon as the first client(s) disconnect.
	# shared: VNC display is shared, i.e. more than one viewer can connect at the same time.
	# noipv6: Do not try to use IPv6 for any listening or connecting sockets.
	# noxdamage: disable X DAMAGE extension warnings
	vnc_password_file="$(mktemp /tmp/x11vnc.pass.XXXXXX)"
	chmod 600 "$vnc_password_file"
	printf '%s\n' "$VNC_PWD" >"$vnc_password_file"
	unset VNC_PWD
	exec /usr/bin/x11vnc -ncache 10 -ncache_cr -passwdfile "$vnc_password_file" -display "$DISPLAY" -rfbport "$vnc_listen_port" -forever -shared -noipv6 -noxdamage
}

start_vnc
