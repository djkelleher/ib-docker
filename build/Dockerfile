# docker build --build-arg PROGRAM=tws -t tws .
FROM ubuntu:24.04

# Build arguments
ARG VERSION=NULL
# program can be tws or ibgateway.
ARG PROGRAM=ibgateway
# release can be stable, latest, or beta;
ARG RELEASE=stable
# arch can be x64 or x86.
ARG ARCH=x64
ARG IBC_VERSION=3.23.0

# Add metadata labels
LABEL description="Interactive Brokers Gateway/TWS Docker Container" \
      version="${VERSION}" \
      program="${PROGRAM}" \
      release="${RELEASE}" \
      ibc.version="${IBC_VERSION}"

# Set locale and language environment variables
ENV LC_ALL=C.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    DISPLAY=:0 \
    PROGRAM=${PROGRAM} \
    IB_RELEASE=${RELEASE} \
    IBC_PATH=/opt/ibc \
    IBC_INI=/opt/ibc/ibc.ini \
    ARCH=${ARCH} \
    VERSION=${VERSION} \
    IBC_VERSION=${IBC_VERSION} \
    HOME=/home/ibuser \
    TWS_SETTINGS_PATH=/home/ibuser/tws_settings \
    XAUTHORITY=/home/ibuser/.Xauthority \
    IB_RELEASE_DIR=/opt/${PROGRAM}/${RELEASE}
    # JavaFX WebKit crash prevention
    #JAVA_TOOL_OPTIONS="-Djava.util.Arrays.useLegacyMergeSort=true -Dcom.sun.webkit.disableHTML5Media=true -Dprism.order=sw" \
    # Enhanced JVM options for stability and crash prevention
    #JAVA_OPTS="-XX:+UseG1GC -XX:+DisableAttachMechanism -Djava.awt.headless=false -Dsun.java2d.xrender=false -Dsun.java2d.pmoffscreen=false -XX:+ExitOnOutOfMemoryError -Djava.net.preferIPv4Stack=true -Dcom.sun.webkit.useHTML5MediaPlayer=false"

# Copy installation script
COPY install.sh /install.sh
# Copy configuration files
COPY config/jts.ini ${HOME}/tws_settings/jts.ini
COPY config/ibc.ini ${IBC_INI}
COPY config/vmoptions.j2 ${HOME}/vmoptions.j2

# Install system dependencies and IB software
RUN chmod +x /install.sh && \
    /install.sh && \
    # Clean up installation script
    rm -f /install.sh && \
    # Create flag file for settings initialization
    touch ${HOME}/init_container_vars

# Copy and set up program scripts
COPY programs/init_container_settings.py /usr/local/bin/init_container_settings
COPY programs/start_xvfb.sh /usr/local/bin/start_xvfb
COPY programs/start_vnc.sh /usr/local/bin/start_vnc
COPY programs/start_ibc.sh /usr/local/bin/start_ibc
COPY programs/ib_utils.sh /usr/local/lib/ib_utils
COPY programs/health_check.sh /usr/local/bin/health_check
# supervisord config
COPY config/supervisord.conf /etc/supervisor/supervisord.conf

# Make all scripts executable
RUN /bin/bash -c "chmod +x /usr/local/bin/{init_container_settings,start_ibc,start_vnc,start_xvfb,health_check} /usr/local/lib/ib_utils"

# Create non-root user for security
RUN groupadd -r ibuser && \
    useradd -r -g ibuser -s /bin/bash -m ibuser

# Set permissions for non-root user
RUN chown -R ibuser:ibuser ${HOME} ${IBC_PATH} && \
    # Set ownership for IB installation directories (now consistently /opt/{PROGRAM})
    chown -R ibuser:ibuser /opt/${PROGRAM} && \
    # Create X11 auth file with proper permissions
    touch ${HOME}/.Xauthority && \
    chown ibuser:ibuser ${HOME}/.Xauthority && \
    chmod 600 ${HOME}/.Xauthority && \
# Create supervisor log directory for non-root user and config directory
    mkdir -p /var/log/supervisor /etc/supervisor/conf.d && \
    chown -R ibuser:ibuser /var/log/supervisor /etc/supervisor/conf.d /etc/supervisor/supervisord.conf

# Improved health check that works with non-root user
HEALTHCHECK --interval=15s --timeout=10s --start-period=45s --retries=3 \
    CMD pgrep -f supervisord >/dev/null 2>&1 || exit 1

# Switch to the non-root user
USER ibuser

# Set working directory for the user
WORKDIR ${HOME}

# Expose VNC port for remote access
EXPOSE 5900

# Run supervisord in foreground (non-daemon mode)
CMD ["/usr/bin/supervisord", "-n"]
