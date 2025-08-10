# Multi-stage, smaller image for IB Gateway/TWS + IBC
# Stage 1: builder - download & install IB software and IBC
FROM debian:bookworm-slim AS builder

ARG VERSION=NULL
ARG PROGRAM=ibgateway       # ibgateway | tws
ARG RELEASE=stable          # stable | latest | beta
ARG ARCH=x64                # x64 only effectively supported here
ARG IBC_VERSION=3.23.0

# Keep only essential build deps in this stage
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    wget ca-certificates unzip locales \
    && rm -rf /var/lib/apt/lists/*

# Locale setup (needed by IB apps)
RUN sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen en_US.UTF-8
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 LANGUAGE=en_US:en

ENV IBC_PATH=/opt/ibc \
    IB_RELEASE_DIR=/opt/${PROGRAM}/${RELEASE}

# Download IB installer
RUN set -eux; \
    mkdir -p "$IB_RELEASE_DIR"; \
    # Ensure target JRE container path exists (will hold bundled or external Java) \
    mkdir -p /opt/i4j_jres; \
    if [ "$VERSION" = "NULL" ]; then \
      URL="https://download2.interactivebrokers.com/installers/${PROGRAM}/${RELEASE}-standalone/${PROGRAM}-${RELEASE}-standalone-linux-${ARCH}.sh"; \
      wget -q -O /ib.sh "$URL"; \
    else \
      FILE="${PROGRAM}-${RELEASE}-${VERSION}-standalone-linux-x64.sh"; \
      URL="https://github.com/DankLabDev/ib-docker/releases/download/${RELEASE}-${VERSION}/$FILE"; \
      # download using original filename so the .sha256 file matches
      wget -q -O "/$FILE" "$URL"; \
      wget -q -O "/$FILE.sha256" "$URL.sha256"; \
      sha256sum --check "/$FILE.sha256"; \
      mv "/$FILE" /ib.sh; \
      rm -f "/$FILE.sha256"; \
    fi; \
    chmod +x /ib.sh; \
    # For aarch64 supply external Java 17 (Zulu), otherwise use bundled Java \
    if [ "$(uname -m)" = "aarch64" ]; then \
      ZULU_NAME="zulu17.52.17-ca-jre17.0.12-linux_aarch64"; \
      wget -q -O /tmp/zulu.tar.gz "https://cdn.azul.com/zulu/bin/${ZULU_NAME}.tar.gz"; \
      tar -xzf /tmp/zulu.tar.gz -C /usr/local/; \
      ln -s /usr/local/${ZULU_NAME} /usr/local/zulu17; \
      app_java_home=/usr/local/zulu17 /ib.sh -q -dir "$IB_RELEASE_DIR"; \
      rm -f /tmp/zulu.tar.gz; \
    else \
      /ib.sh -q -dir "$IB_RELEASE_DIR"; \
    fi; \
    rm -f /ib.sh

# Install IBC
RUN set -eux; \
    wget -q -O /tmp/IBC.zip "https://github.com/IbcAlpha/IBC/releases/download/${IBC_VERSION}/IBCLinux-${IBC_VERSION}.zip"; \
    unzip /tmp/IBC.zip -d "$IBC_PATH"; \
    chmod -R u+x ${IBC_PATH}/*.sh ${IBC_PATH}/scripts/*.sh || true; \
    rm -f /tmp/IBC.zip

# Prune unneeded files (logs, docs caches) to save space
RUN find "$IB_RELEASE_DIR" -type f -name "*.log" -delete || true

# Stage 2: runtime - only runtime dependencies
FROM debian:bookworm-slim AS runtime
ARG PROGRAM=ibgateway
ARG RELEASE=stable
ARG VERSION=NULL
ARG IBC_VERSION=3.23.0

LABEL org.opencontainers.image.title="Interactive Brokers ${PROGRAM}" \
      org.opencontainers.image.description="Interactive Brokers ${PROGRAM} (${RELEASE}) with IBC ${IBC_VERSION}" \
      org.opencontainers.image.vendor="DankLabs" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/DankLabDev/ib-docker" \
      org.opencontainers.image.licenses="MIT"

# Install only runtime packages
# xset needed (x11-xserver-utils); xauth & openssl for X11 cookie + random; procps for pgrep (healthcheck); xvfb, x11vnc, supervisor for services.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates locales \
      xvfb x11vnc supervisor \
      openssl x11-xserver-utils xauth procps \
      libx11-6 libxrender1 libxtst6 libnss3 libnspr4 \
      tini \
    && rm -rf /var/lib/apt/lists/*

# Only install extra GUI/libs if building TWS (keep layer small for gateway)
RUN if [ "$PROGRAM" = "tws" ]; then \
      apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        libgtk-3-0 libasound2 libxss1 libxcomposite1 libxdamage1 libxrandr2 libxkbcommon0 \
        libpangocairo-1.0-0 libpango-1.0-0 libcairo2 libatspi2.0-0 libatk1.0-0 \
        libdrm2 libgbm1 fontconfig fonts-dejavu-core \
        && rm -rf /var/lib/apt/lists/*; \
    fi

# Locale
RUN sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen en_US.UTF-8
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 LANGUAGE=en_US:en

ENV DISPLAY=:0 \
    IBC_PATH=/opt/ibc \
    IBC_INI=/opt/ibc/ibc.ini \
    HOME=/home/ibuser \
    TWS_SETTINGS_PATH=/home/ibuser/tws_settings \
    XAUTHORITY=/home/ibuser/.Xauthority \
    IB_RELEASE=${RELEASE} \
    IB_RELEASE_DIR=/opt/${PROGRAM}/${RELEASE} \
    PROGRAM=${PROGRAM} \
    IBC_VERSION=${IBC_VERSION} \
    VERSION=${VERSION}

# Create non-root user early so we can chown on COPY
RUN groupadd -r ibuser && useradd -r -g ibuser -s /bin/bash -m ibuser \
    && mkdir -p /tmp/.X11-unix \
    && chown root:root /tmp/.X11-unix \
    && chmod 1777 /tmp/.X11-unix

# Copy installed software from builder (owned by ibuser)
COPY --from=builder --chown=ibuser:ibuser /opt/${PROGRAM} /opt/${PROGRAM}
COPY --from=builder --chown=ibuser:ibuser /opt/ibc /opt/ibc
# Copy bundled JRE directory created by installer (empty for gateway if not used but path exists)
COPY --from=builder --chown=ibuser:ibuser /opt/i4j_jres /opt/i4j_jres

# Copy configuration & scripts
COPY --chown=ibuser:ibuser config/jts.ini ${HOME}/tws_settings/jts.ini
COPY --chown=ibuser:ibuser config/ibc.ini ${IBC_INI}
COPY --chown=ibuser:ibuser config/vmoptions.j2 ${HOME}/vmoptions.j2
COPY --chown=root:root config/supervisord.conf /etc/supervisor/supervisord.conf
COPY --chown=root:root programs/init_container_settings.py /usr/local/bin/init_container_settings
COPY --chown=root:root programs/start_xvfb.sh /usr/local/bin/start_xvfb
COPY --chown=root:root programs/start_vnc.sh /usr/local/bin/start_vnc
COPY --chown=root:root programs/start_ibc.sh /usr/local/bin/start_ibc
COPY --chown=root:root programs/ib_utils.sh /usr/local/lib/ib_utils

RUN chmod +x /usr/local/bin/init_container_settings /usr/local/bin/start_xvfb /usr/local/bin/start_vnc /usr/local/bin/start_ibc /usr/local/lib/ib_utils \
    && mkdir -p /var/log/supervisor /etc/supervisor/conf.d \
    && chown -R ibuser:ibuser /var/log/supervisor /etc/supervisor

USER ibuser
WORKDIR /home/ibuser

# Healthcheck: ensure supervisord running AND Xvfb display active
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 CMD pgrep -f supervisord >/dev/null 2>&1 && xset q >/dev/null 2>&1 || exit 1

EXPOSE 5900

ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf", "-n"]
