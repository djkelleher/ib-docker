#!/bin/bash
# SSH tunnel startup script for supervisord

set -Eo pipefail

# Source SSH utilities
source /usr/local/lib/ib_utils

# Check if SSH tunnel is enabled
if [ "$SSH_TUNNEL" != "yes" ] && [ "$SSH_TUNNEL" != "both" ]; then
	echo ".> SSH tunnel disabled, exiting"
	exit 0
fi

echo ".> SSH tunnel enabled (mode: $SSH_TUNNEL)"

# Set up ports and SSH configuration
set_ports
setup_ssh

# Check if we can start tunnel
if [ -z "$SSH_USER_TUNNEL" ]; then
	echo ".> SSH_USER_TUNNEL not set, cannot start tunnel"
	exit 1
fi

if ! pgrep ssh-agent >/dev/null && [ -n "$SSH_PASSPHRASE" ]; then
	echo ".> ssh-agent not running but SSH_PASSPHRASE is set"
	exit 1
fi

# Set up tunnel parameters
if [ -z "$SSH_REMOTE_PORT" ]; then
	SSH_REMOTE_PORT="$API_PORT"
fi

_SSH_OPTIONS="-o ServerAliveInterval=${SSH_ALIVE_INTERVAL:-20}"
_SSH_OPTIONS+=" -o ServerAliveCountMax=${SSH_ALIVE_COUNT:-3}"

if [ -n "$SSH_OPTIONS" ]; then
	_SSH_OPTIONS+=" $SSH_OPTIONS"
fi

# Set up VNC/RDP tunnel if requested
_SCREEN=""
if [ "${PROGRAM:-gateway}" = "gateway" ] && [ -n "$SSH_VNC_PORT" ] && pgrep x11vnc >/dev/null; then
	_SCREEN="-R 127.0.0.1:5900:localhost:$SSH_VNC_PORT"
	echo ".> SSH VNC tunnel enabled: ${_SCREEN}"
elif [ "${PROGRAM:-gateway}" = "tws" ] && [ -n "$SSH_RDP_PORT" ]; then
	_SCREEN="-R 127.0.0.1:3389:localhost:$SSH_RDP_PORT"
	echo ".> SSH RDP tunnel enabled: ${_SCREEN}"
fi

echo ".> Starting SSH tunnel: ${SSH_USER_TUNNEL}"
echo ".> Local port: ${API_PORT}, Remote port: ${SSH_REMOTE_PORT}"

# Start SSH tunnel - this becomes the main process that supervisord monitors
exec ssh ${_SSH_OPTIONS} -TNR 127.0.0.1:${API_PORT}:localhost:${SSH_REMOTE_PORT} ${_SCREEN} ${SSH_USER_TUNNEL}
