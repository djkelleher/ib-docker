#!/bin/bash
log() {
	#local timestamp
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp  $1"
}

ensure_env() {
	local name="$1"

	if [ -z "${!name:-}" ]; then
		log "ERROR: Required environment variable ${name} is not set"
		exit 1
	fi
}

file_env() {
	local name="$1"
	local file_name="${name}_FILE"
	local default="${2:-}"
	local value="$default"

	if [ -n "${!name:-}" ] && [ -n "${!file_name:-}" ]; then
		log "ERROR: ${name} and ${file_name} are mutually exclusive"
		exit 1
	fi

	if [ -n "${!name:-}" ]; then
		value="${!name}"
	elif [ -n "${!file_name:-}" ]; then
		if [ ! -r "${!file_name}" ] || [ ! -f "${!file_name}" ]; then
			log "ERROR: ${file_name} is not a readable file: ${!file_name}"
			exit 1
		fi
		value="$(<"${!file_name}")"
	fi

	export "$name=$value"
}

unset_file_env() {
	local name="$1"
	local file_name="${name}_FILE"

	if [ -n "${!file_name:-}" ]; then
		unset "$name"
	fi
}

run_script_dir() {
	local name="$1"
	local phase="$2"
	local scripts_dir="${!name:-}"
	local script_path
	local scripts=()

	if [ -z "$scripts_dir" ]; then
		log "${phase} hooks disabled (${name} is not set)"
		return 0
	fi

	case "$scripts_dir" in
	/*) ;;
	*)
		log "ERROR: ${name} must be an absolute path: ${scripts_dir}"
		return 1
		;;
	esac

	if [ ! -d "$scripts_dir" ]; then
		log "ERROR: ${phase} hook directory does not exist: ${scripts_dir}"
		return 1
	fi

	shopt -s nullglob
	scripts=("$scripts_dir"/*.sh)
	shopt -u nullglob
	if [ "${#scripts[@]}" -eq 0 ]; then
		log "${phase} hook directory has no .sh scripts: ${scripts_dir}"
		return 0
	fi

	for script_path in "${scripts[@]}"; do
		if [ ! -x "$script_path" ]; then
			log "ERROR: ${phase} hook is not executable: ${script_path}"
			return 1
		fi
		log "Running ${phase} hook: ${script_path}"
		"$script_path"
	done
}

ensure_absolute_path() {
	local name="$1"
	local value

	ensure_env "$name"
	value="${!name}"

	case "$value" in
	/*) ;;
	*)
		log "ERROR: ${name} must be an absolute path: ${value}"
		exit 1
		;;
	esac
}

ensure_executable_file() {
	local path="$1"
	local label="$2"

	if [ ! -x "$path" ]; then
		log "ERROR: ${label} is missing or not executable: ${path}"
		exit 1
	fi
}

ensure_file() {
	local path="$1"
	local label="$2"

	if [ ! -f "$path" ]; then
		log "ERROR: ${label} is missing: ${path}"
		exit 1
	fi
}

ensure_directory_path() {
	local path="$1"
	local label="$2"

	if [ -e "$path" ] && [ ! -d "$path" ]; then
		log "ERROR: ${label} is not a directory: ${path}"
		exit 1
	fi
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

ib_trading_mode() {
	case "${TRADING_MODE:-paper}" in
	paper)
		printf '%s\n' "paper"
		;;
	live)
		printf '%s\n' "live"
		;;
	*)
		log "ERROR: Unsupported TRADING_MODE: ${TRADING_MODE}"
		exit 1
		;;
	esac
}

ib_twofa_timeout_action() {
	case "${TWOFA_TIMEOUT_ACTION:-exit}" in
	exit)
		printf '%s\n' "exit"
		;;
	restart)
		printf '%s\n' "restart"
		;;
	*)
		log "ERROR: Unsupported TWOFA_TIMEOUT_ACTION: ${TWOFA_TIMEOUT_ACTION}"
		exit 1
		;;
	esac
}

ibc_version() {
	ensure_env IBC_VERSION
	if [[ ! $IBC_VERSION =~ ^[0-9]+[.][0-9]+[.][0-9]+$ ]]; then
		log "ERROR: IBC_VERSION must look like 3.23.0: ${IBC_VERSION}"
		exit 1
	fi
	printf '%s\n' "$IBC_VERSION"
}

resolve_ib_release_dir() {
	local release_dir="${IB_RELEASE_DIR:-}"
	local app_name
	local ib_release

	app_name="$(ib_product_executable)"
	if [ -z "$release_dir" ]; then
		ensure_env IB_RELEASE
		ib_release="$IB_RELEASE"
		release_dir="/opt/${app_name}/${ib_release}"
	fi

	case "$release_dir" in
	/*) ;;
	*)
		log "ERROR: IB release directory must be an absolute path: ${release_dir}"
		exit 1
		;;
	esac

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
	local app_name
	local product_dir

	app_name="$(ib_product_executable)"
	product_dir="$(dirname "$release_dir")"

	if [ "$app_name" = "ibgateway" ]; then
		if [ "$(basename "$product_dir")" != "ibgateway" ]; then
			log "ERROR: Gateway release directory must be nested under an ibgateway directory: ${release_dir}"
			log "IBC resolves Gateway as <tws-path>/ibgateway/<release>"
			exit 1
		fi
		# IBC appends /ibgateway/<version> for Gateway, but only /<version> for TWS.
		dirname "$product_dir"
	else
		if [ "$(basename "$product_dir")" != "tws" ]; then
			log "ERROR: TWS release directory must be nested under a tws directory: ${release_dir}"
			log "IBC resolves TWS as <tws-path>/<release>"
			exit 1
		fi
		printf '%s\n' "$product_dir"
	fi
}

ib_release_version_from_dir() {
	local release_dir="$1"

	basename "$release_dir"
}

x_display_number() {
	local display="${1:-${DISPLAY:-:1}}"
	local display_no

	display_no="${display##*:}"
	display_no="${display_no%%.*}"

	if [[ ! $display_no =~ ^[0-9]+$ ]]; then
		log "ERROR: Invalid DISPLAY value: ${display}"
		exit 1
	fi

	printf '%s\n' "$display_no"
}

validate_x_display() {
	local display="${1:-${DISPLAY:-:1}}"
	local display_no

	display_no="${display##*:}"
	display_no="${display_no%%.*}"

	if [[ ! $display_no =~ ^[0-9]+$ ]]; then
		log "ERROR: Invalid DISPLAY value: ${display}"
		exit 1
	fi
}

x_server_display() {
	local display="${1:-${DISPLAY:-:1}}"

	if [[ ! $display =~ ^:[0-9]+([.][0-9]+)?$ ]]; then
		log "ERROR: Invalid X server DISPLAY value: ${display}"
		log "Expected a local server display such as :1 or :1.0"
		exit 1
	fi

	printf '%s\n' "$display"
}

x_screen_dimension() {
	local dimension="${VNC_SCREEN_DIMENSION:-1600x1200x24}"

	if [[ ! $dimension =~ ^[1-9][0-9]*x[1-9][0-9]*x[1-9][0-9]*$ ]]; then
		log "ERROR: Invalid VNC_SCREEN_DIMENSION: ${dimension}"
		log "Expected format: WIDTHxHEIGHTxDEPTH, for example 1600x1200x24"
		exit 1
	fi

	printf '%s\n' "$dimension"
}

vnc_port() {
	local port="${VNC_PORT:-5900}"

	if [[ ! $port =~ ^[1-9][0-9]*$ ]] || ((port > 65535)); then
		log "ERROR: Invalid VNC_PORT: ${port}"
		log "Expected an integer from 1 to 65535"
		exit 1
	fi

	printf '%s\n' "$port"
}

x_display_process_pattern() {
	local process_name="$1"
	local display="${2:-${DISPLAY:-:1}}"
	local display_no

	display_no="$(x_display_number "$display")"
	printf '%s.*:%s([[:space:].]|$)\n' "$process_name" "$display_no"
}

wait_for_x_server() {
	DISPLAY="${DISPLAY:-:1}"
	export DISPLAY

	log "Waiting for X server on display ${DISPLAY}..."
	validate_x_display "$DISPLAY"
	ensure_absolute_path HOME
	ensure_directory_path "$HOME" "HOME"

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
