#!/bin/bash
set -euo pipefail

source /usr/local/lib/ib_utils

start_ibc() {
	local app_name
	local home_dir
	local ibc_version
	local ibc_args=()
	local ibc_pid

	app_name="$(ib_product_executable)"
	TRADING_MODE="$(ib_trading_mode)"
	TWOFA_TIMEOUT_ACTION="$(ib_twofa_timeout_action)"
	ibc_version="$(ibc_version)"
	ensure_absolute_path IBC_PATH
	ensure_absolute_path IBC_INI
	ensure_executable_file "${IBC_PATH}/scripts/ibcstart.sh" "IBC start script"
	ensure_file "$IBC_INI" "IBC config"
	if [ "$app_name" = "ibgateway" ]; then
		ibc_args+=("-g")
	fi
	IB_RELEASE_DIR="$(resolve_ib_release_dir)"
	IB_RELEASE="$(ib_release_version_from_dir "$IB_RELEASE_DIR")"
	IB_BASE_DIR="$(resolve_ibc_tws_path "$IB_RELEASE_DIR")"
	ensure_absolute_path HOME
	ensure_directory_path "$HOME" "HOME"
	home_dir="$HOME"
	TWS_SETTINGS_PATH="${TWS_SETTINGS_PATH:-${home_dir}/tws_settings}"
	ensure_absolute_path TWS_SETTINGS_PATH
	ensure_directory_path "$TWS_SETTINGS_PATH" "TWS settings path"
	mkdir -p "$TWS_SETTINGS_PATH"

	# Set up X11 environment for IBC
	export XAUTHORITY="$HOME/.Xauthority"
	wait_for_x_server
	run_script_dir X_SCRIPTS "X"

	log ".> Starting IBC in ${TRADING_MODE} mode, with params:"
	echo ".>		Version: ${IB_RELEASE}"
	echo ".>		IBC version: ${ibc_version}"
	echo ".>		program: ${app_name}"
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
		"--tws-settings-path=${TWS_SETTINGS_PATH}" &
	ibc_pid="$!"

	trap 'kill "$ibc_pid" 2>/dev/null || true; wait "$ibc_pid" 2>/dev/null || true; exit 143' TERM INT
	trap 'status=$?; kill "$ibc_pid" 2>/dev/null || true; wait "$ibc_pid" 2>/dev/null || true; exit "$status"' ERR

	run_script_dir IBC_SCRIPTS "IBC"
	wait "$ibc_pid"
}

start_ibc
