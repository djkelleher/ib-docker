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
    ARCH=${ARCH}

# Copy installation script first (changes less frequently)
COPY install.sh /install.sh

# Install system dependencies and IB software
RUN chmod +x /install.sh && \
    /install.sh && \
    # Clean up installation script
    rm -f /install.sh && \
    # Create flag file for settings initialization
    touch /init_container_vars

# Create non-root user for security
RUN groupadd -r ibuser && \
    useradd -r -g ibuser -s /bin/bash ibuser && \
    mkdir -p /home/ibuser

# Copy configuration files
COPY config/jts.ini /jts.ini
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY config/ibc.ini ${IBC_INI}

# Copy and set up program scripts
COPY programs/common.sh /common.sh
COPY programs/init_container_settings.py /usr/local/bin/init_container_settings
COPY programs/start_xvfb.sh /usr/local/bin/start_xvfb
COPY programs/start_vnc.sh /usr/local/bin/start_vnc
COPY programs/start_ibc.sh /usr/local/bin/start_ibc

# Make all scripts executable
RUN chmod +x /usr/local/bin/{init_container_settings,start_ibc,start_vnc,start_xvfb}

# Set permissions for non-root user
RUN chown -R ibuser:ibuser /home/ibuser /opt/ibc /jts.ini

# Switch to the non-root user
USER ibuser

# Set working directory for the user
WORKDIR /home/ibuser

# Expose VNC port for remote access
EXPOSE 5900

# Improved health check that works with non-root user
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD pgrep -f supervisord >/dev/null 2>&1 || exit 1

# Run supervisord in foreground (non-daemon mode)
CMD ["/usr/bin/supervisord", "-n"]
