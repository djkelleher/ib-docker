# Multi-stage, smaller image for IB Gateway/TWS + IBC
# Stage 1: builder - download & install IB software and IBC
FROM debian:bookworm-slim@sha256:67b30a61dc87758f0caf819646104f29ecbda97d920aaf5edc834128ac8493d3 AS builder

ARG TARGETARCH=amd64
ARG TARGET_PLATFORM=
ARG IB_VERSION=NULL
# ibgateway | tws
ARG PROGRAM=ibgateway
# stable | latest | beta
ARG RELEASE=stable
# IB publishes x64 installer artifacts; arm64 builds run Gateway with external Java.
ARG IB_INSTALLER_ARCH=x64
ARG IBC_VERSION=3.23.0

RUN set -eu; \
    target_platform="${TARGET_PLATFORM:-linux/$TARGETARCH}"; \
    case "$TARGETARCH" in amd64|arm64) ;; *) echo "Unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; esac; \
    case "$target_platform" in linux/amd64|linux/arm64) ;; *) echo "Unsupported TARGET_PLATFORM: $target_platform" >&2; exit 1 ;; esac; \
    if [ "$target_platform" != "linux/$TARGETARCH" ]; then \
      echo "TARGET_PLATFORM must match TARGETARCH: TARGET_PLATFORM=$target_platform TARGETARCH=$TARGETARCH" >&2; \
      exit 1; \
    fi; \
    case "$PROGRAM" in ibgateway|tws) ;; *) echo "Unsupported PROGRAM: $PROGRAM" >&2; exit 1 ;; esac; \
    case "$RELEASE" in stable|latest|beta) ;; *) echo "Unsupported RELEASE: $RELEASE" >&2; exit 1 ;; esac; \
    if [ "$PROGRAM" = "tws" ] && [ "$TARGETARCH" != "amd64" ]; then \
      echo "TWS images are only supported for linux/amd64" >&2; \
      exit 1; \
    fi; \
    if [ -z "$IB_VERSION" ]; then \
      echo "IB_VERSION must be NULL or a packaged IB version" >&2; \
      exit 1; \
    fi; \
    if [ "$IB_VERSION" != "NULL" ] && ! printf '%s' "$IB_VERSION" | grep -Eqz '^[0-9]+[.][0-9]+[.][0-9]+[a-z]?$'; then \
      echo "IB_VERSION must look like 10.45.1e or be NULL: $IB_VERSION" >&2; \
      exit 1; \
    fi; \
    if [ -z "$IBC_VERSION" ]; then \
      echo "IBC_VERSION must not be empty" >&2; \
      exit 1; \
    fi; \
    if ! printf '%s' "$IBC_VERSION" | grep -Eqz '^[0-9]+[.][0-9]+[.][0-9]+$'; then \
      echo "IBC_VERSION must look like 3.23.0: $IBC_VERSION" >&2; \
      exit 1; \
    fi; \
    if [ "$IB_INSTALLER_ARCH" != "x64" ]; then \
      echo "IB installer artifacts are only supported with IB_INSTALLER_ARCH=x64" >&2; \
      exit 1; \
    fi

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
    mkdir -p /opt/i4j_jres /usr/local/zulu17; \
    if [ "$IB_VERSION" = "NULL" ]; then \
      URL="https://download2.interactivebrokers.com/installers/${PROGRAM}/${RELEASE}-standalone/${PROGRAM}-${RELEASE}-standalone-linux-${IB_INSTALLER_ARCH}.sh"; \
      wget -nv --tries=3 --timeout=30 -O /ib.sh "$URL"; \
    else \
      FILE="${PROGRAM}-${RELEASE}-${IB_VERSION}-standalone-linux-${IB_INSTALLER_ARCH}.sh"; \
      URL="https://github.com/djkelleher/ib-docker/releases/download/${RELEASE}-${IB_VERSION}/$FILE"; \
      # download using original filename so the .sha256 file matches
      wget -nv --tries=3 --timeout=30 -O "/$FILE" "$URL"; \
      wget -nv --tries=3 --timeout=30 -O "/$FILE.sha256" "$URL.sha256"; \
      CHECKSUM_FILE="$(sed -E 's/^[^[:space:]]+[[:space:]]+[*]?//' "/$FILE.sha256")"; \
      if [ "$CHECKSUM_FILE" != "$FILE" ]; then \
        echo "Checksum sidecar does not reference expected file $FILE: $CHECKSUM_FILE" >&2; \
        exit 1; \
      fi; \
      sha256sum --strict --check "/$FILE.sha256"; \
      mv "/$FILE" /ib.sh; \
      rm -f "/$FILE.sha256"; \
    fi; \
    chmod +x /ib.sh; \
    # For arm64 supply external Java 17 (Zulu), otherwise use bundled Java \
    if [ "$TARGETARCH" = "arm64" ]; then \
      ZULU_NAME="zulu17.52.17-ca-jre17.0.12-linux_aarch64"; \
      wget -nv --tries=3 --timeout=30 -O /tmp/zulu.tar.gz "https://cdn.azul.com/zulu/bin/${ZULU_NAME}.tar.gz"; \
      tar -xzf /tmp/zulu.tar.gz -C /usr/local/; \
      cp -a /usr/local/${ZULU_NAME}/. /usr/local/zulu17/; \
      app_java_home=/usr/local/zulu17 /ib.sh -q -dir "$IB_RELEASE_DIR"; \
      rm -f /tmp/zulu.tar.gz; \
    else \
      /ib.sh -q -dir "$IB_RELEASE_DIR"; \
    fi; \
    rm -f /ib.sh

# Verify the installer extracted the expected offline layout. IBC relies on these
# paths and product-specific filenames when constructing its classpath.
RUN set -eux; \
    test -d "$IB_RELEASE_DIR/jars"; \
    test -x "$IB_RELEASE_DIR/$PROGRAM"; \
    test -f "$IB_RELEASE_DIR/$PROGRAM.vmoptions"; \
    test -d "$IB_RELEASE_DIR/.install4j"; \
    if [ "$PROGRAM" = "ibgateway" ]; then \
      test "$(dirname "$(dirname "$IB_RELEASE_DIR")")" = "/opt"; \
    else \
      test "$(dirname "$IB_RELEASE_DIR")" = "/opt/tws"; \
    fi

# Install IBC
RUN set -eux; \
    wget -nv --tries=3 --timeout=30 -O /tmp/IBC.zip "https://github.com/IbcAlpha/IBC/releases/download/${IBC_VERSION}/IBCLinux-${IBC_VERSION}.zip"; \
    unzip /tmp/IBC.zip -d "$IBC_PATH"; \
    find "$IBC_PATH" -type f -name "*.sh" -exec chmod u+x {} +; \
    test -x "$IBC_PATH/scripts/ibcstart.sh"; \
    rm -f /tmp/IBC.zip

# Prune unneeded files (logs, docs caches) to save space
RUN find "$IB_RELEASE_DIR" -type f -name "*.log" -delete || true

# Stage 2: runtime - only runtime dependencies
FROM debian:bookworm-slim@sha256:67b30a61dc87758f0caf819646104f29ecbda97d920aaf5edc834128ac8493d3 AS runtime
ARG TARGETARCH=amd64
ARG TARGET_PLATFORM=
ARG PROGRAM=ibgateway
ARG RELEASE=stable
ARG IB_VERSION=NULL
ARG IBC_VERSION=3.23.0

RUN set -eu; \
    target_platform="${TARGET_PLATFORM:-linux/$TARGETARCH}"; \
    case "$TARGETARCH" in amd64|arm64) ;; *) echo "Unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; esac; \
    case "$target_platform" in linux/amd64|linux/arm64) ;; *) echo "Unsupported TARGET_PLATFORM: $target_platform" >&2; exit 1 ;; esac; \
    if [ "$target_platform" != "linux/$TARGETARCH" ]; then \
      echo "TARGET_PLATFORM must match TARGETARCH: TARGET_PLATFORM=$target_platform TARGETARCH=$TARGETARCH" >&2; \
      exit 1; \
    fi; \
    case "$PROGRAM" in ibgateway|tws) ;; *) echo "Unsupported PROGRAM: $PROGRAM" >&2; exit 1 ;; esac; \
    case "$RELEASE" in stable|latest|beta) ;; *) echo "Unsupported RELEASE: $RELEASE" >&2; exit 1 ;; esac; \
    if [ "$PROGRAM" = "tws" ] && [ "$TARGETARCH" != "amd64" ]; then \
      echo "TWS images are only supported for linux/amd64" >&2; \
      exit 1; \
    fi; \
    if [ -z "$IB_VERSION" ]; then \
      echo "IB_VERSION must be NULL or a packaged IB version" >&2; \
      exit 1; \
    fi; \
    if [ "$IB_VERSION" != "NULL" ] && ! printf '%s' "$IB_VERSION" | grep -Eqz '^[0-9]+[.][0-9]+[.][0-9]+[a-z]?$'; then \
      echo "IB_VERSION must look like 10.45.1e or be NULL: $IB_VERSION" >&2; \
      exit 1; \
    fi; \
    if [ -z "$IBC_VERSION" ]; then \
      echo "IBC_VERSION must not be empty" >&2; \
      exit 1; \
    fi; \
    if ! printf '%s' "$IBC_VERSION" | grep -Eqz '^[0-9]+[.][0-9]+[.][0-9]+$'; then \
      echo "IBC_VERSION must look like 3.23.0: $IBC_VERSION" >&2; \
      exit 1; \
    fi

LABEL org.opencontainers.image.title="Interactive Brokers ${PROGRAM}" \
      org.opencontainers.image.description="Interactive Brokers ${PROGRAM} (${RELEASE}) with IBC ${IBC_VERSION}" \
      org.opencontainers.image.vendor="DankLabs" \
      org.opencontainers.image.version="${IB_VERSION}" \
      org.opencontainers.image.source="https://github.com/djkelleher/ib-docker" \
      org.opencontainers.image.licenses="MIT"

# Install only runtime packages
# xset needed (x11-xserver-utils); xauth & openssl for X11 cookie + random; procps for pgrep (healthcheck); xvfb, x11vnc, supervisor for services.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates locales \
      xvfb x11vnc supervisor \
      openssl x11-xserver-utils xauth procps \
      libx11-6 libxrender1 libxtst6 libnss3 libnspr4 \
      tini coreutils \
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

ENV DISPLAY=:1 \
    IBC_PATH=/opt/ibc \
    IBC_INI=/opt/ibc/ibc.ini \
    HOME=/home/ibuser \
    TWS_SETTINGS_PATH=/home/ibuser/tws_settings \
    XAUTHORITY=/home/ibuser/.Xauthority \
    IB_RELEASE=${RELEASE} \
    IB_RELEASE_DIR=/opt/${PROGRAM}/${RELEASE} \
    PROGRAM=${PROGRAM} \
    IBC_VERSION=${IBC_VERSION} \
    IB_VERSION=${IB_VERSION}

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
# Copy external arm64 JRE path; empty on amd64, populated when TARGETARCH=arm64.
COPY --from=builder --chown=ibuser:ibuser /usr/local/zulu17 /usr/local/zulu17

# Copy configuration & scripts
COPY --chown=ibuser:ibuser config/jts.ini ${HOME}/tws_settings/jts.ini
COPY --chown=ibuser:ibuser config/jts.ini ${HOME}/tws_settings/jts.ini.template
COPY --chown=ibuser:ibuser config/ibc.ini ${IBC_INI}
COPY --chown=ibuser:ibuser config/ibc.ini ${IBC_INI}.template
COPY --chown=ibuser:ibuser config/vmoptions.j2 ${HOME}/vmoptions.j2
COPY --chown=root:root config/supervisord.conf /etc/supervisor/supervisord.conf
COPY --chown=root:root programs/init_container_settings.py /usr/local/bin/init_container_settings
COPY --chown=root:root programs/start_xvfb.sh /usr/local/bin/start_xvfb
COPY --chown=root:root programs/start_vnc.sh /usr/local/bin/start_vnc
COPY --chown=root:root programs/start_ibc.sh /usr/local/bin/start_ibc
COPY --chown=root:root programs/ib_utils.sh /usr/local/lib/ib_utils
COPY --chown=root:root programs/entrypoint.sh /usr/local/bin/entrypoint

RUN chmod +x /usr/local/bin/init_container_settings /usr/local/bin/start_xvfb /usr/local/bin/start_vnc /usr/local/bin/start_ibc /usr/local/lib/ib_utils /usr/local/bin/entrypoint \
    && mkdir -p /var/log/supervisor /etc/supervisor/conf.d \
    && chown -R ibuser:ibuser /var/log/supervisor

USER ibuser
WORKDIR /home/ibuser

# Healthcheck: ensure supervised core services are running and Xvfb display is active
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 CMD supervisorctl status xvfb ibc | awk '/^xvfb[[:space:]]+RUNNING/{xvfb=1} /^ibc[[:space:]]+RUNNING/{ibc=1} END{exit !(xvfb && ibc)}' && xset q >/dev/null 2>&1 || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf", "-n"]
