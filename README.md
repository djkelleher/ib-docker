# Interactive Brokers Gateway/TWS Docker

<p align="center">
  <img height="300" src="./.logo.jpg">
</p>

[![Daily Release Check](https://github.com/DankLabDev/ib-docker/actions/workflows/release.yml/badge.svg)](https://github.com/DankLabDev/ib-docker/actions/workflows/release.yml)
[![Gateway Build](https://github.com/DankLabDev/ib-docker/actions/workflows/build_gateway.yml/badge.svg)](https://github.com/DankLabDev/ib-docker/actions/workflows/build_gateway.yml)
[![TWS Build](https://github.com/DankLabDev/ib-docker/actions/workflows/build_tws.yml/badge.svg)](https://github.com/DankLabDev/ib-docker/actions/workflows/build_tws.yml)


Reliable high-performance docker images to run Interactive Brokers Gateway and TWS without any human interaction.

**Gateway:**
`docker pull danklabs/ib-gateway`
**TWS:**
`docker pull danklabs/ib-tws`

There are two Docker images here, one for IB Gateway ([stable](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php) and [latest](https://www.interactivebrokers.com/en/trading/ibgateway-latest.php)), and the other for Trader Workstation ([stable](https://www.interactivebrokers.com/en/trading/tws-offline-stable.php) and [latest](https://www.interactivebrokers.com/en/trading/tws-offline-latest.php)).
Both images include:
- [IBC](https://github.com/IbcAlpha/IBC) - to control IB Gateway (simulates user input).
- [Xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml) - an X11 virtual framebuffer to run graphics applications without graphics hardware.
- [x11vnc](https://wiki.archlinux.org/title/x11vnc) - a VNC server to interact with TWS or IB Gateway user interface.

## Usage
The sample [docker-compose.yml](./docker-compose.yml) file documents the environmental variables that can be used to configure containers.

For practical purposes, you should be able to configure containers with the provided environmental variables, but if needed/desired you can mount a volume with a custom config file for [Interactive Brokers Controller (IBC)](https://github.com/IbcAlpha/IBC). The file should be mounted to `/opt/ibc/ibc.ini`
e.g.
```bash
volumes:
    - $HOME/ibc.ini:/opt/ibc/ibc.ini
```
The [ibc.empty.ini](./ibc.empty.ini) is an empty template configuration file that you can use for this purpose.

If desired, you can also mount volumes for custom TWS/Gateway jts.ini files:

Program | Release    | Mount to |
-------- | -------- | ------- |
Gateway | Stable  | /opt/ibgateway/latest/jts.ini    |
Gateway | Latest | /opt/ibgateway/stable/jts.ini     |
TWS | Stable | /Jts/stable/jts.ini |
TWS | Latest | /Jts/latest/jts.ini |


## Setup

```yaml
services:
  ib-gateway:
    # ib-gateway or ib-tws. latest or stable.
    image: ib-gateway:latest
    restart: always
    build:
      context: .
      dockerfile: Dockerfile
      args:
        - PROGRAM=ibgateway # or tws
        - RELEASE=latest # or stable
    network_mode: host
    environment:
      # User `uid` to run the container as (1000 is host user)
      PUID: 1000
      # User `gid` to run the container as (1000 is host user)
      PGID: 1000
      # VNC server password. If not defined, then VNC server will NOT start.
      VNC_PWD: ${VNC_PWD}
      VNC_SCREEN_DIMENSION: ${VNC_SCREEN_DIMENSION:-1600x1200x16}
      DISPLAY: :1
      TZ: ${TIME_ZONE:-America/New_York}
      TIME_ZONE: ${TIME_ZONE:-America/New_York}
      # Set Java heap, default 768MB, TWS might need more. Proposed value 1024. Enter just the number, don't enter units, ex mb. See [Increase Memory Size for TWS](https://ibkrguides.com/tws/usersguidebook/priceriskanalytics/custommemory.htm)
      JAVA_HEAP_SIZE: ${JAVA_HEAP_SIZE:-}
      ## IBC variables ##
      # The TWS username.
      IB_USER: ${IB_USER}
      # The TWS password.
      IB_PASSWORD: ${IB_PASSWORD}
      # live or paper.
      TRADING_MODE: ${TRADING_MODE:-paper}
      # TWS_SETTINGS_PATH` is set and stored in a volume, jts.ini will already exists so this will not be used. Examples `Europe/Paris`, `America/New_York`, `Asia/Tokyo`
      TWS_SETTINGS_PATH: ${TWS_SETTINGS_PATH:-}
      # yes or no. See https://github.com/IbcAlpha/IBC/blob/master/userguide.md
      READ_ONLY_API: ${READ_ONLY_API:-no}
      # 'exit' or 'restart', set to 'restart if you set `AUTO_RESTART_TIME`. See IBC [documentation](https://github.com/IbcAlpha/IBC/blob/master/userguide.md#second-factor-authentication)
      TWOFA_TIMEOUT_ACTION: ${TWOFA_TIMEOUT_ACTION:-exit}
      # time to restart IB Gateway, does not require daily 2FA validation. format hh:mm AM/PM. See IBC [documentation](https://github.com/IbcAlpha/IBC/blob/master/userguide.md#ibc-user-guide)
      AUTO_RESTART_TIME: ${AUTO_RESTART_TIME:-}
      # Auto-Logoff: at a specified time, TWS shuts down tidily, without restarting
      AUTO_LOGOFF_TIME: ${AUTO_LOGOFF_TIME:-}
      # a time (specified in your local timeframe) that is after 01:00 US/Eastern. When
      # this time is reached on Sundays, IBC tidily closes TWS, and the script then
      # reloads IBC thus starting a new instance of TWS and initiating the usual full logon.
      COLD_RESTART_TIME: ${COLD_RESTART_TIME:-}
      # Settings relate to the corresponding 'Precautions' checkboxes in the API section of the Global Configuration dialog. Accepted values `yes`, `no` if not set, the existing TWS/Gateway configuration is unchanged
      BYPASS_WARNING: ${BYPASS_WARNING:-yes}
      # automatically save its settings on a schedule of your choosing. You can specify one or more specific times, ex `SaveTwsSettingsAt=08:00   12:30 17:30`
      SAVE_TWS_SETTINGS: ${SAVE_TWS_SETTINGS:-Every 30 mins}
      # support relogin after timeout. See IBC [documentation](https://github.com/IbcAlpha/IBC/blob/master/userguide.md#second-factor-authentication)
      RELOGIN_AFTER_TWOFA_TIMEOUT: ${RELOGIN_AFTER_TWOFA_TIMEOUT:-no}
      TWOFA_EXIT_INTERVAL: ${TWOFA_EXIT_INTERVAL:-60}

```
