#!/bin/bash
log() {
	#local timestamp
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp  $1"
}

wait_for_x_server() {
	log "Waiting for X server on display ${DISPLAY}..."

	# Set up X11 environment
	XAUTHORITY="$HOME/.Xauthority"
	export XAUTHORITY

	# Wait for X server to be ready (xvfb should be started by supervisord)
	timeout=60
	while [ $timeout -gt 0 ]; do
		if xset q >/dev/null 2>&1; then
			log "X server is ready on ${DISPLAY}"
			break
		fi

		# Every 10 seconds, log progress to show we're still waiting
		if [ $((timeout % 10)) -eq 0 ]; then
			log "Waiting for X server to start... ($timeout seconds remaining)"
		fi

		sleep 1
		timeout=$((timeout - 1))
	done

	if [ $timeout -eq 0 ]; then
		log "ERROR: X server failed to start within 60 seconds on ${DISPLAY}"
		log "Check if xvfb service is running properly"
		exit 1
	fi
}
