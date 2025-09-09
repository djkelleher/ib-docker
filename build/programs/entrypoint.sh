#!/bin/bash

# Container entrypoint script to handle initialization and cleanup

log() {
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "$timestamp [ENTRYPOINT] $1"
}

find_available_display() {
    # Find an available display number starting from 1
    # Skip :0 as it's commonly used by host systems
    for display_num in {1..99}; do
        # Check if lock file or socket exists
        if [ ! -f "/tmp/.X${display_num}-lock" ] && [ ! -S "/tmp/.X11-unix/X${display_num}" ]; then
            echo ":${display_num}"
            return 0
        fi
    done
    # Fallback to :99 if nothing else is available
    echo ":99"
}

cleanup_x_server() {
    log "Performing initial X server cleanup..."
    
    # Kill any existing X server processes
    pkill -9 -f "Xvfb" 2>/dev/null || true
    pkill -9 -f "x11vnc" 2>/dev/null || true
    
    # Clean up X server files and locks
    rm -rf /tmp/.X*-lock 2>/dev/null || true
    rm -rf /tmp/.X11-unix/* 2>/dev/null || true
    rm -rf /var/run/X* 2>/dev/null || true
    rm -rf /var/lock/X* 2>/dev/null || true
    
    # Recreate X11 directory with correct permissions
    mkdir -p /tmp/.X11-unix
    chmod 1777 /tmp/.X11-unix
    
    log "X server cleanup completed"
}

# Perform initial cleanup
cleanup_x_server

# Determine the best available display
# If DISPLAY is not set or is :0 (which might conflict), find an available one
if [ -z "$DISPLAY" ] || [ "$DISPLAY" = ":0" ]; then
    DISPLAY=$(find_available_display)
    log "Auto-selected available display: $DISPLAY"
else
    log "Using provided display: $DISPLAY"
fi

export DISPLAY

log "Starting supervisord with DISPLAY=$DISPLAY"

# Execute the original command (supervisord)
exec "$@"