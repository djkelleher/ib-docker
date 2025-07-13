#!/bin/bash

source /usr/local/lib/ib_utils

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
	TWS_SETTINGS_PATH="${HOME}/tws_settings"
	mkdir -p "$TWS_SETTINGS_PATH"

	# Set up X11 environment for IBC
	export XAUTHORITY="$HOME/.Xauthority"
	wait_for_x_server

	log ".> Starting IBC in ${TRADING_MODE} mode, with params:"
	echo ".>		Version: ${IB_RELEASE}"
	echo ".>		program: ${PROGRAM}"
	echo ".>		tws-path: ${IB_BASE_DIR}"
	echo ".>		ibc-path: ${IBC_PATH}"
	echo ".>		ibc-init: ${IBC_INI}"
	echo ".>		tws-settings-path: ${TWS_SETTINGS_PATH}"
	echo ".>		on2fatimeout: ${TWOFA_TIMEOUT_ACTION}"

	# start IBC -g for gateway
	"${IBC_PATH}/scripts/ibcstart.sh" "${IB_RELEASE}" ${PROGRAM_FLAG} \
		"--tws-path=${IB_BASE_DIR}" \
		"--ibc-ini=${IBC_INI}" \
		"--ibc-path=${IBC_PATH}" \
		"--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
		"--tws-settings-path=${TWS_SETTINGS_PATH}"
}

start_ibc
