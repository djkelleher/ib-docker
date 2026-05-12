#!/bin/bash

source /usr/local/lib/ib_utils

start_ibc() {
	local ibc_args=()

	TRADING_MODE="$(ib_trading_mode)"
	TWOFA_TIMEOUT_ACTION="$(ib_twofa_timeout_action)"
	if [ "$PROGRAM" = "ibgateway" ]; then
		ibc_args+=("-g")
	fi
	IB_RELEASE_DIR="$(resolve_ib_release_dir)"
	IB_BASE_DIR="$(resolve_ibc_tws_path "$IB_RELEASE_DIR")"
	TWS_SETTINGS_PATH="${TWS_SETTINGS_PATH:-${HOME}/tws_settings}"
	mkdir -p "$TWS_SETTINGS_PATH"

	# Set up X11 environment for IBC
	export XAUTHORITY="$HOME/.Xauthority"
	wait_for_x_server

	log ".> Starting IBC in ${TRADING_MODE} mode, with params:"
	echo ".>		Version: ${IB_RELEASE}"
	echo ".>		IBC version: ${IBC_VERSION}"
	echo ".>		program: ${PROGRAM}"
	echo ".>		ib-release-dir: ${IB_RELEASE_DIR}"
	echo ".>		tws-path: ${IB_BASE_DIR}"
	echo ".>		ibc-path: ${IBC_PATH}"
	echo ".>		ibc-init: ${IBC_INI}"
	echo ".>		tws-settings-path: ${TWS_SETTINGS_PATH}"
	echo ".>		on2fatimeout: ${TWOFA_TIMEOUT_ACTION}"

	# start IBC with -g for gateway
	"${IBC_PATH}/scripts/ibcstart.sh" "${IB_RELEASE}" "${ibc_args[@]}" \
		"--tws-path=${IB_BASE_DIR}" \
		"--ibc-ini=${IBC_INI}" \
		"--ibc-path=${IBC_PATH}" \
		"--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
		"--tws-settings-path=${TWS_SETTINGS_PATH}"
}

start_ibc
