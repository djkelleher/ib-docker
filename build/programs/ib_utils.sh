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

# SSH tunnel setup and management functions

# usage: file_env VAR [DEFAULT]
#    ie: file_env 'XYZ_DB_PASSWORD' 'example'
# (will allow for "$XYZ_DB_PASSWORD_FILE" to fill in the value of
#  "$XYZ_DB_PASSWORD" from a file, especially for Docker's secrets feature)
file_env() {
	local var="$1"
	local fileVar="${var}_FILE"
	local def="${2:-}"
	if [ "${!var:-}" ] && [ "${!fileVar:-}" ]; then
		printf >&2 'error: both %s and %s are set (but are exclusive)\n' "$var" "$fileVar"
		exit 1
	fi
	local val="$def"
	if [ "${!var:-}" ]; then
		val="${!var}"
	elif [ "${!fileVar:-}" ]; then
		val="$(<"${!fileVar}")"
	fi
	export "$var"="$val"
}

# usage: unset_env VAR
#	ie: unset_env 'XYZ_DB_PASSWORD'
unset_env() {
	local var="$1"
	local fileVar="${var}_FILE"
	if [ "${!fileVar:-}" ]; then
		unset "$var"
	fi
}

set_ports() {
	# set ports for API and tunnel based on program and trading mode

	if [ "${PROGRAM:-gateway}" = "gateway" ]; then
		if [ "$TRADING_MODE" = "paper" ]; then
			# paper ibgateway ports
			API_PORT=4002
			SOCAT_PORT=4004
		elif [ "$TRADING_MODE" = "live" ]; then
			# live ibgateway ports
			API_PORT=4001
			SOCAT_PORT=4003
		else
			echo ".> Invalid TRADING_MODE: $TRADING_MODE"
			exit 1
		fi
	elif [ "${PROGRAM:-gateway}" = "tws" ]; then
		if [ "$TRADING_MODE" = "paper" ]; then
			# paper TWS ports
			API_PORT=7497
			SOCAT_PORT=7499
		elif [ "$TRADING_MODE" = "live" ]; then
			# live TWS ports
			API_PORT=7496
			SOCAT_PORT=7498
		else
			echo ".> Invalid TRADING_MODE: $TRADING_MODE"
			exit 1
		fi
	fi
	export API_PORT SOCAT_PORT
	echo ".> API_PORT set to: ${API_PORT}"
	echo ".> SOCAT_PORT set to: ${SOCAT_PORT}"
}

setup_ssh() {
	# prepare SSH Tunnel
	if [ "$SSH_TUNNEL" = "yes" ] || [ "$SSH_TUNNEL" = "both" ]; then
		echo ".> Setting up SSH tunnel"

		_SSH_OPTIONS="-o ServerAliveInterval=${SSH_ALIVE_INTERVAL:-20}"
		_SSH_OPTIONS+=" -o ServerAliveCountMax=${SSH_ALIVE_COUNT:-3}"

		if [ -n "$SSH_OPTIONS" ]; then
			_SSH_OPTIONS+=" $SSH_OPTIONS"
		fi
		SSH_ALL_OPTIONS="$_SSH_OPTIONS"
		export SSH_ALL_OPTIONS
		echo ".> SSH options: $SSH_ALL_OPTIONS"

		file_env 'SSH_PASSPHRASE'
		if [ -n "$SSH_PASSPHRASE" ]; then
			if ! pgrep ssh-agent >/dev/null; then
				# start agent if it's not already running
				echo ".> Starting ssh-agent."
				ssh-agent >"${HOME}/.ssh-agent.env"
				# shellcheck disable=SC1090
				source "${HOME}/.ssh-agent.env"
				echo ".> ssh-agent sock: ${SSH_AUTH_SOCK}"
			else
				echo ".> ssh-agent already running"
				if [ -z "${SSH_AUTH_SOCK}" ]; then
					echo ".> Loading agent environment"
					# shellcheck disable=SC1090
					source "${HOME}/.ssh-agent.env"
				fi
				echo ".> ssh-agent sock: ${SSH_AUTH_SOCK}"
			fi

			if ls "${HOME}"/.ssh/id_* >/dev/null 2>&1; then
				echo ".> Adding keys to ssh-agent."
				export SSH_ASKPASS_REQUIRE=never
				SSHPASS="${SSH_PASSPHRASE}" sshpass -e -P "passphrase" ssh-add
				unset_env 'SSH_PASSPHRASE'
				echo ".> ssh-agent identities: $(ssh-add -l)"
			else
				echo ".> SSH keys not found, ssh-agent not started"
			fi
		fi
	else
		echo ".> SSH tunnel disabled"
	fi
}
