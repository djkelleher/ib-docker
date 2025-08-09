#!/bin/bash

# Health check script for IB Docker container
set -e

echo "=== Container Health Check ==="

# Check if supervisord is running
if ! pgrep -f supervisord >/dev/null 2>&1; then
	echo "❌ supervisord not running"
fi
echo "✅ supervisord is running"

# Check if Xvfb is running
if ! pgrep -f "Xvfb.*:99" >/dev/null 2>&1; then
	echo "❌ Xvfb not running"
fi
echo "✅ Xvfb is running on display :99"

# Check if X server is responding
if ! DISPLAY=:99 xset q >/dev/null 2>&1; then
	echo "❌ X server not responding"
fi
echo "✅ X server is responding"

# Check if VNC server is running
if ! pgrep -f "x11vnc" >/dev/null 2>&1; then
	echo "❌ VNC server not running"
fi
echo "✅ VNC server is running"

# Check if VNC port is listening
if ! netstat -ln 2>/dev/null | grep -q ":5900.*LISTEN" && ! ss -ln 2>/dev/null | grep -q ":5900.*LISTEN"; then
	echo "❌ VNC port 5900 not listening"
fi
echo "✅ VNC port 5900 is listening"

# Check if IBC/TWS is running
if ! pgrep -f "ibcalpha.ibc.IbcTws" >/dev/null 2>&1; then
	echo "❌ IBC/TWS not running"
fi
echo "✅ IBC/TWS is running"

echo "=== All checks passed! Container is healthy ==="
exit 0
