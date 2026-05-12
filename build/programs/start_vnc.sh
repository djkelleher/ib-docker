#!/bin/bash
set -euo pipefail

source /usr/local/lib/ib_utils

cleanup_vnc_password_file() {
	local path="$1"

	if [ -n "$path" ] && [ -f "$path" ]; then
		rm -f "$path"
	fi
}

stop_vnc() {
	local path="$1"
	local pid="$2"

	cleanup_vnc_password_file "$path"
	kill "$pid" 2>/dev/null || true
	wait "$pid" 2>/dev/null || true
	exit 143
}

start_vnc() {
	local vnc_password_file
	local vnc_listen_port
	local vnc_pid
	local -a x11vnc_args

	if [[ -z ${VNC_PWD:-} ]]; then
		log "VNC password is not set (VNC_PWD). VNC is disabled."
		exec sleep infinity
	fi
	log "Found VNC password (VNC_PWD). Starting VNC."
	ensure_absolute_path HOME
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
	trap 'cleanup_vnc_password_file "$vnc_password_file"' EXIT
	x11vnc_args=(
		-ncache 10
		-ncache_cr
		-passwdfile "$vnc_password_file"
		-display "$DISPLAY"
		-rfbport "$vnc_listen_port"
		-forever
		-shared
		-noipv6
		-noxdamage
	)
	/usr/bin/x11vnc "${x11vnc_args[@]}" &
	vnc_pid="$!"
	trap 'stop_vnc "$vnc_password_file" "$vnc_pid"' TERM INT
	sleep 2
	cleanup_vnc_password_file "$vnc_password_file"
	wait "$vnc_pid"
}

start_vnc
