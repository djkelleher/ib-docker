#!/bin/bash

log() {
	#local timestamp
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp  $1"
}

start_ibc() {
	# use arg -g or -gateway to start gateway.
	# extract major version from desktop file.
	#major_v=$(ls $IB_PATH/*.desktop | sed -E 's/[^0-9]+//g')
	if [ "$PROGRAM" = "ibgateway" ]; then
		PROGRAM_FLAG="-g"
		IB_BASE_DIR=/opt
	else
		PROGRAM_FLAG=""
		IB_BASE_DIR=/Jts
	fi
	TWS_SETTINGS_PATH=${HOME}/tws_settings
	mkdir -p $TWS_SETTINGS_PATH

	log ".> Starting IBC in ${TRADING_MODE} mode, with params:"
	echo ".>		Version: ${IB_RELEASE}"
	echo ".>		program: ${PROGRAM}"
	echo ".>		tws-path: ${IB_BASE_DIR}"
	echo ".>		ibc-path: ${IBC_PATH}"
	echo ".>		ibc-init: ${IBC_INI}"
	echo ".>		tws-settings-path: ${TWS_SETTINGS_PATH}"
	echo ".>		on2fatimeout: ${TWOFA_TIMEOUT_ACTION}"
	
	# Wait for DISPLAY to be available from xvfb service
	timeout=30
	while [ $timeout -gt 0 ]; do
		if [ -f "/tmp/display_info" ]; then
			DISPLAY=$(cat /tmp/display_info)
			export DISPLAY
			log "Found DISPLAY from xvfb: $DISPLAY"
			break
		fi
		sleep 1
		timeout=$((timeout - 1))
	done
	
	# Set up X11 environment for IBC
	export XAUTHORITY=$HOME/.Xauthority
	
	# Wait for X server to be available - more robust check
	timeout=120
	while [ $timeout -gt 0 ]; do
		if DISPLAY=$DISPLAY xset q >/dev/null 2>&1; then
			log "X server is ready for IBC"
			break
		fi
		log "Waiting for X server to be available for IBC... ($timeout seconds remaining)"
		sleep 1
		timeout=$((timeout - 1))
	done
	
	if [ $timeout -eq 0 ]; then
		log "ERROR: X server not available for IBC after 120 seconds"
		exit 1
	fi
	
	# start IBC -g for gateway
	"${IBC_PATH}/scripts/ibcstart.sh" "${IB_RELEASE}" ${PROGRAM_FLAG} \
		"--tws-path=${IB_BASE_DIR}" \
		"--ibc-ini=${IBC_INI}" \
		"--ibc-path=${IBC_PATH}" \
		"--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
		"--tws-settings-path=${TWS_SETTINGS_PATH:-}"
}

start_ibc
