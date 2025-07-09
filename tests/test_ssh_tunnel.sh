#!/bin/bash
# Test script for SSH tunnel functionality

set -e

echo "=== IB Docker SSH Tunnel Test ==="

# Check if container is running
if ! docker-compose ps | grep -q "Up"; then
	echo "❌ Container is not running. Start it with: docker-compose up -d"
	exit 1
fi

echo "✅ Container is running"

# Check if SSH tunnel is enabled
SSH_TUNNEL=$(docker-compose exec -T ib-gateway bash -c 'echo $SSH_TUNNEL' | tr -d '\r')

if [ "$SSH_TUNNEL" = "yes" ] || [ "$SSH_TUNNEL" = "both" ]; then
	echo "✅ SSH tunnel is enabled (mode: $SSH_TUNNEL)"

	# Check if SSH process is running
	if docker-compose exec -T ib-gateway pgrep ssh >/dev/null; then
		echo "✅ SSH process is running"
	else
		echo "❌ SSH process is not running"
		echo "Check logs with: docker-compose logs ib-gateway"
		exit 1
	fi

	# Check if ssh-agent is running
	if docker-compose exec -T ib-gateway pgrep ssh-agent >/dev/null; then
		echo "✅ SSH agent is running"
	else
		echo "⚠️  SSH agent is not running (may be OK if no passphrase)"
	fi

else
	echo "ℹ️  SSH tunnel is disabled"
fi

# Check if socat is running (should run unless SSH_TUNNEL=yes)
if [ "$SSH_TUNNEL" != "yes" ]; then
	if docker-compose exec -T ib-gateway pgrep socat >/dev/null; then
		echo "✅ Socat is running for local port forwarding"
	else
		echo "❌ Socat is not running"
		exit 1
	fi
else
	echo "ℹ️  Socat disabled (SSH tunnel only mode)"
fi

# Check if IBC/TWS is running
if docker-compose exec -T ib-gateway pgrep java >/dev/null; then
	echo "✅ IBC/TWS Java process is running"
else
	echo "❌ IBC/TWS is not running"
	exit 1
fi

# Check API port accessibility
API_PORT=$(docker-compose exec -T ib-gateway bash -c 'source /usr/local/lib/ib_utils && set_ports && echo $API_PORT' | tr -d '\r')
echo "ℹ️  API port: $API_PORT"

# Test local connection (if socat is running)
if [ "$SSH_TUNNEL" != "yes" ]; then
	if timeout 5 bash -c "</dev/tcp/localhost/$API_PORT" 2>/dev/null; then
		echo "✅ Local API port $API_PORT is accessible"
	else
		echo "⚠️  Local API port $API_PORT is not yet accessible (may need more time to start)"
	fi
fi

echo ""
echo "=== Service Status ==="
docker-compose exec -T ib-gateway supervisorctl status

echo ""
echo "=== Recent Logs ==="
docker-compose logs --tail=20 ib-gateway

echo ""
echo "=== Test Complete ==="

if [ "$SSH_TUNNEL" = "yes" ] || [ "$SSH_TUNNEL" = "both" ]; then
	echo "ℹ️  To test SSH tunnel from remote machine:"
	SSH_USER_TUNNEL=$(docker-compose exec -T ib-gateway bash -c 'echo $SSH_USER_TUNNEL' | tr -d '\r')
	SSH_REMOTE_PORT=$(docker-compose exec -T ib-gateway bash -c 'echo ${SSH_REMOTE_PORT:-$API_PORT}' | tr -d '\r')

	if [ -n "$SSH_USER_TUNNEL" ]; then
		echo "   telnet ${SSH_USER_TUNNEL#*@} ${SSH_REMOTE_PORT}"
	fi
fi
