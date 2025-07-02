FROM ubuntu:24.04

# Build arguments
ARG VERSION=NULL
# program can be tws or ibgateway.
ARG PROGRAM=ibgateway
# release can be stable, latest, or beta;
ARG RELEASE=stable
# arch can be x64 or x86.
ARG ARCH=x64
ARG IBC_VERSION=3.22.0

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
    PROGRAM=${PROGRAM} \
    IB_RELEASE=${RELEASE} \
    IBC_PATH=/opt/ibc \
    IBC_INI=/opt/ibc/ibc.ini \
    ARCH=${ARCH} \
    VERSION=${VERSION} \
    IBC_VERSION=${IBC_VERSION} \
    IB_RELEASE_DIR="" \
    HOME=/home/ibuser \
    TWS_SETTINGS_PATH=/home/ibuser/tws_settings \
    SUPERVISORD_UI_USER="" \
    SUPERVISORD_UI_PASS="" \
    SUPERVISORD_UI_PORT=9001 \
    JAVA_OPTS="-XX:+UnlockExperimentalVMOptions -XX:+UseCGroupMemoryLimitForHeap -XX:+UseContainerSupport -Djava.security.egd=file:/dev/./urandom -XX:+DisableAttachMechanism"

# Copy installation script
COPY install.sh /install.sh
# Copy configuration files
COPY config/jts.ini ${HOME}/tws_settings/jts.ini
COPY config/ibc.ini ${IBC_INI}

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
COPY programs/ssh_utils.sh /usr/local/lib/ssh_utils
COPY programs/run_socat.sh /usr/local/bin/run_socat
COPY programs/start_ssh.sh /usr/local/bin/start_ssh
COPY programs/start_socat.sh /usr/local/bin/start_socat
# supervisord config
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Make all scripts executable
RUN /bin/bash -c "chmod +x /usr/local/bin/{init_container_settings,start_ibc,start_vnc,start_xvfb,run_socat,start_ssh,start_socat} /usr/local/lib/ssh_utils"

# Create non-root user for security
RUN groupadd -r ibuser && \
    useradd -r -g ibuser -s /bin/bash ibuser

# Set permissions for non-root user
RUN chown -R ibuser:ibuser ${HOME} ${IBC_PATH} && \
    # Set ownership for IB installation directories
    if [ "${PROGRAM}" = "ibgateway" ]; then \
        chown -R ibuser:ibuser /opt/ibgateway; \
    else \
        chown -R ibuser:ibuser /Jts; \
    fi

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
