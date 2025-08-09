#!/bin/bash
log() {
	#local timestamp
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp  $1"
}

wait_for_x_server() {
	log "Waiting for xvfb DISPLAY..."

	# Wait for DISPLAY to be available from xvfb service
	timeout=30
	while [ $timeout -gt 0 ]; do
		# Check if we can read the DISPLAY from a shared location
		if [ -f "/tmp/display_info" ] && [ -s "/tmp/display_info" ]; then
			DISPLAY=$(cat /tmp/display_info 2>/dev/null)
			if [ -n "$DISPLAY" ] && [[ $DISPLAY =~ ^:[0-9]+$ ]]; then
				export DISPLAY
				log "Found DISPLAY from xvfb: $DISPLAY"
				break
			else
				log "Invalid DISPLAY format in /tmp/display_info: $DISPLAY"
			fi
		fi
		sleep 1
		timeout=$((timeout - 1))
	done

	if [ $timeout -eq 0 ]; then
		log "Could not find valid DISPLAY from xvfb"
		exit 1
	fi

	# Set up X11 environment
	XAUTHORITY="$HOME/.Xauthority"
	export XAUTHORITY

	# Wait for X server to be ready
	timeout=30
	while [ $timeout -gt 0 ]; do
		if xset q >/dev/null 2>&1; then
			log "X server is ready"
			break
		fi
		log "Waiting for X server to start... ($timeout seconds remaining)"
		sleep 1
		timeout=$((timeout - 1))
	done

	if [ $timeout -eq 0 ]; then
		log "ERROR: X server failed to start within 60 seconds"
		exit 1
	fi
}

set_ports() {
	# set ports for API based on program and trading mode

	if [ "${PROGRAM:-gateway}" = "gateway" ]; then
		if [ "$TRADING_MODE" = "paper" ]; then
			# paper ibgateway ports
			API_PORT=4002
		elif [ "$TRADING_MODE" = "live" ]; then
			# live ibgateway ports
			API_PORT=4001
		else
			echo ".> Invalid TRADING_MODE: $TRADING_MODE"
			exit 1
		fi
	elif [ "${PROGRAM:-gateway}" = "tws" ]; then
		if [ "$TRADING_MODE" = "paper" ]; then
			# paper TWS ports
			API_PORT=7497
		elif [ "$TRADING_MODE" = "live" ]; then
			# live TWS ports
			API_PORT=7496
		else
			echo ".> Invalid TRADING_MODE: $TRADING_MODE"
			exit 1
		fi
	fi
	export API_PORT
	echo ".> API_PORT set to: ${API_PORT}"
}
