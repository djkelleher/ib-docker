#!/bin/bash
log() {
	#local timestamp
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp  $1"
}

ib_product_executable() {
	case "${PROGRAM:-}" in
	ibgateway)
		printf '%s\n' "ibgateway"
		;;
	tws)
		printf '%s\n' "tws"
		;;
	*)
		log "ERROR: Unsupported IB program: ${PROGRAM:-<unset>}"
		exit 1
		;;
	esac
}

resolve_ib_release_dir() {
	local release_dir="${IB_RELEASE_DIR:-}"
	local app_name

	if [ -z "$release_dir" ]; then
		release_dir="/opt/${PROGRAM}/${IB_RELEASE}"
	fi

	app_name="$(ib_product_executable)"

	if [ ! -d "$release_dir/jars" ]; then
		log "ERROR: IB release directory is invalid: ${release_dir}"
		log "Expected to find jars under ${release_dir}/jars"
		exit 1
	fi

	if [ ! -x "$release_dir/$app_name" ]; then
		log "ERROR: IB release directory is invalid: ${release_dir}"
		log "Expected executable ${release_dir}/${app_name}"
		exit 1
	fi

	if [ ! -f "$release_dir/${app_name}.vmoptions" ]; then
		log "ERROR: IB release directory is invalid: ${release_dir}"
		log "Expected vmoptions file ${release_dir}/${app_name}.vmoptions"
		exit 1
	fi

	printf '%s\n' "$release_dir"
}

resolve_ibc_tws_path() {
	local release_dir="$1"
	local product_dir

	product_dir="$(dirname "$release_dir")"

	if [ "$PROGRAM" = "ibgateway" ] && [ "$(basename "$product_dir")" = "ibgateway" ]; then
		# IBC appends /ibgateway/<version> for Gateway, but only /<version> for TWS.
		dirname "$product_dir"
	else
		printf '%s\n' "$product_dir"
	fi
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
