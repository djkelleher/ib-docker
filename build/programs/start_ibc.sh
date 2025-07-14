#!/bin/bash

source /usr/local/lib/ib_utils

start_ibc() {
	# use arg -g or -gateway to start gateway.
	# extract major version from desktop file.
	#major_v=$(ls $IB_PATH/*.desktop | sed -E 's/[^0-9]+//g')
	if [ "$PROGRAM" = "ibgateway" ]; then
		PROGRAM_FLAG="-g"
		IB_BASE_DIR=/opt
	else
		PROGRAM_FLAG=""
		IB_BASE_DIR=/Jts
	fi
	TWS_SETTINGS_PATH="${HOME}/tws_settings"
	mkdir -p "$TWS_SETTINGS_PATH"

	# Set up X11 environment for IBC
	export XAUTHORITY="$HOME/.Xauthority"
	wait_for_x_server

	# Set JVM options to prevent crashes
	if [ -n "$JAVA_OPTS" ]; then
		export TWS_JAVA_OPTS="$JAVA_OPTS"
		export IBC_JAVA_OPTS="$JAVA_OPTS"
	fi

	# Enhanced JVM stability options to prevent SIGSEGV crashes
	STABILITY_OPTS="-XX:+UseG1GC -XX:+UnlockExperimentalVMOptions -XX:+UseStringDeduplication"
	STABILITY_OPTS="$STABILITY_OPTS -XX:+ExitOnOutOfMemoryError -XX:+HeapDumpOnOutOfMemoryError"
	STABILITY_OPTS="$STABILITY_OPTS -XX:HeapDumpPath=/tmp/java_crash.hprof"
	STABILITY_OPTS="$STABILITY_OPTS -XX:+DisableAttachMechanism"
	STABILITY_OPTS="$STABILITY_OPTS -Djava.awt.headless=false"
	STABILITY_OPTS="$STABILITY_OPTS -Dsun.java2d.xrender=false"
	STABILITY_OPTS="$STABILITY_OPTS -Dsun.java2d.pmoffscreen=false"

	# JavaFX WebKit crash prevention
	STABILITY_OPTS="$STABILITY_OPTS -Dprism.order=sw"
	STABILITY_OPTS="$STABILITY_OPTS -Djavafx.platform=desktop"
	STABILITY_OPTS="$STABILITY_OPTS -Dprism.vsync=false"
	STABILITY_OPTS="$STABILITY_OPTS -Dcom.sun.javafx.isEmbedded=false"
	STABILITY_OPTS="$STABILITY_OPTS -Dcom.sun.javafx.virtual.keyboard=none"

	# WebKit media handling fixes
	STABILITY_OPTS="$STABILITY_OPTS -Dcom.sun.webkit.useHTML5MediaPlayer=false"
	STABILITY_OPTS="$STABILITY_OPTS -Dcom.sun.webkit.disableHTML5Media=true"
	STABILITY_OPTS="$STABILITY_OPTS -Djava.util.Arrays.useLegacyMergeSort=true"

	export JAVA_OPTS="$JAVA_OPTS $STABILITY_OPTS"
	export TWS_JAVA_OPTS="$JAVA_OPTS"
	export IBC_JAVA_OPTS="$JAVA_OPTS"

	# Additional crash prevention measures
	ulimit -c unlimited # Enable core dumps for debugging
	ulimit -n 65536     # Increase file descriptor limit
	ulimit -v unlimited # Remove virtual memory limits
	export _JAVA_OPTIONS="$JAVA_OPTS"

	# Disable problematic X11 features that can cause JNI crashes
	export LIBGL_ALWAYS_INDIRECT=1
	export LIBGL_ALWAYS_SOFTWARE=1
	export QT_X11_NO_MITSHM=1
	export GDK_SYNCHRONIZE=1

	# Additional JavaFX/WebKit crash prevention
	export PRISM_ORDER=sw
	export PRISM_VSYNC=false
	export WEBKIT_DISABLE_COMPOSITING_MODE=1
	export JAVA_TOOL_OPTIONS="-Djava.util.Arrays.useLegacyMergeSort=true"

	log ".> Starting IBC in ${TRADING_MODE} mode, with params:"
	echo ".>		Version: ${IB_RELEASE}"
	echo ".>		program: ${PROGRAM}"
	echo ".>		tws-path: ${IB_BASE_DIR}"
	echo ".>		ibc-path: ${IBC_PATH}"
	echo ".>		ibc-init: ${IBC_INI}"
	echo ".>		tws-settings-path: ${TWS_SETTINGS_PATH}"
	echo ".>		on2fatimeout: ${TWOFA_TIMEOUT_ACTION}"

	# start IBC -g for gateway
	"${IBC_PATH}/scripts/ibcstart.sh" "${IB_RELEASE}" ${PROGRAM_FLAG} \
		"--tws-path=${IB_BASE_DIR}" \
		"--ibc-ini=${IBC_INI}" \
		"--ibc-path=${IBC_PATH}" \
		"--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
		"--tws-settings-path=${TWS_SETTINGS_PATH}"
}

start_ibc
