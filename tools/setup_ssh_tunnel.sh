#!/bin/bash
# setup_ssh_tunnel.sh

set -e

CLIENT_HOST="$1"
CLIENT_USER="$2"

if [ $# -ne 2 ]; then
	echo "Usage: $0 <client_host> <client_user>"
	exit 1
fi

# Generate SSH key
ssh-keygen -t ed25519 -f ~/.ssh/ib_tunnel -N ""

# Copy key to client
ssh-copy-id -i ~/.ssh/ib_tunnel.pub "${CLIENT_USER}@${CLIENT_HOST}"

# Update .env file
cat >>.env <<EOF
SSH_TUNNEL=yes
SSH_USER_TUNNEL=${CLIENT_USER}@${CLIENT_HOST}
SSH_REMOTE_PORT=4001
EOF

echo "SSH tunnel configured for ${CLIENT_USER}@${CLIENT_HOST}"
