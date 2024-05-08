#!/bin/bash

log() {
    #local timestamp
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "$timestamp  $1"
}

DISPLAY=${DISPLAY:-:0}
export DISPLAY

start_xvfb() {
    echo "Starting Xvfb server"
    display_no=$(echo "$DISPLAY" | sed 's/^://')
    rm -f /tmp/.X${display_no}-lock
    rm -r /tmp/.X11-unix
    VNC_SCREEN_DIMENSION=${VNC_SCREEN_DIMENSION:-1280x1024x16}
    log "Starting virtual frame buffer. Display $DISPLAY. Screen dimension: $VNC_SCREEN_DIMENSION"
    ## start virtual frame buffer.
    # creates screen screennum and sets its width, height, and depth to W, H, and D respectively. By default, only screen 0 exists and has the dimensions 1280x1024x8.
    /usr/bin/Xvfb $DISPLAY -ac -screen 0 $VNC_SCREEN_DIMENSION &
    log "Virtual frame buffer started."
}

start_vnc() {
    if [[ -z "$VNC_PWD" ]]; then
        log "VNC password is not set (VNC_PWD). Will not start VNC."
        return
    else
        log "Found VNC password (VNC_PWD)."
    fi
    log "Starting VNC server. Display $DISPLAY"
    ## start VNC server.
    # display: X11 server display to connect to.
    # forever: Keep listening for more connections rather than exiting as soon as the first client(s) disconnect.
    # shared: VNC display is shared, i.e. more than one viewer can connect at the same time.
    # bg: Go into the background after screen setup. Messages to stderr are lost unless -o logfile is used.
    # noipv6: Do not try to use IPv6 for any listening or connecting sockets.
    # logappend: Write stderr messages to file logfile instead of to the terminal.
    /usr/bin/x11vnc -ncache 10 -ncache_cr -passwd $VNC_PWD -display $DISPLAY -forever -shared -bg -noipv6 -logappend /var/log/x11vnc.log &
    log "VNC server started."
}

process_env_vars() {
    # check if we need to apply environment variables.
    if [ -f "/process_env_vars" ]; then
        echo "Appling environment variables."
        # replace env variables
        envsubst <"${IBC_INI}" >tmp.ini && mv tmp.ini "${IBC_INI}"
        if [ ${PROGRAM} = "ibgateway" ]; then
            IB_INI=/opt/ibgateway/${IB_RELEASE}/jts.ini
        else
            IB_INI=/Jts/jts.ini
        fi
        envsubst <"${IB_INI}" >tmp.ini && mv tmp.ini "${IB_INI}"
        # where are settings stored
        if [ -n "$TWS_SETTINGS_PATH" ]; then
            echo "Settings directory set to: $TWS_SETTINGS_PATH"
            if [ ! -d "$TWS_SETTINGS_PATH" ]; then
                # if TWS_SETTINGS_PATH does not exists, create it
                echo "Creating directory: $TWS_SETTINGS_PATH"
                mkdir "$TWS_SETTINGS_PATH"
            fi
            mv $IB_INI $TWS_SETTINGS_PATH/jts.ini
        fi
        # set java heap size in vm options
        if [ -n "${JAVA_HEAP_SIZE}" ]; then
            _string="s/-Xmx768m/-Xmx${JAVA_HEAP_SIZE}m/g"
            sed -i "${_string}" "${IB_VMOPTIONS}"
            echo "Java heap size set to ${JAVA_HEAP_SIZE}m"
        else
            echo "Using default Java heap size 768m."
        fi
        # file so we don't run this again.
        rm /process_env_vars
    fi
}

start_common() {
    start_xvfb
    start_vnc
    process_env_vars
}

start_ibc() {
    # use arg -g or -gateway to start gateway.
    # extract major version from desktop file.
    #major_v=$(ls $IB_PATH/*.desktop | sed -E 's/[^0-9]+//g')
    echo ".> Starting IBC in ${TRADING_MODE} mode, with params:"
    echo ".>		Version: ${IB_RELEASE}"
    echo ".>		program: ${1}"
    echo ".>		tws-path: ${IB_BASE_DIR}"
    echo ".>		ibc-path: ${IBC_PATH}"
    echo ".>		ibc-init: ${IBC_INI}"
    echo ".>		tws-settings-path: ${TWS_SETTINGS_PATH}"
    echo ".>		on2fatimeout: ${TWOFA_TIMEOUT_ACTION}"
    if [ $1 = "-g" ]; then
        IB_BASE_DIR=/opt
    else
        IB_BASE_DIR=/Jts
    fi
    # start IBC -g for gateway
    "${IBC_PATH}/scripts/ibcstart.sh" "${IB_RELEASE}" $1 \
        "--tws-path=${IB_BASE_DIR}" \
        "--ibc-ini=${IBC_INI}" \
        "--ibc-path=${IBC_PATH}" \
        "--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
        "--tws-settings-path=${TWS_SETTINGS_PATH:-}"
    echo "IBC started."
}
