# Interactive Brokers Gateway/TWS Docker

<p align="center">
  <img height="300" src="./.logo.jpg">
</p>

[![Daily Release Check](https://github.com/djkelleher/ib-docker/actions/workflows/release.yml/badge.svg)](https://github.com/djkelleher/ib-docker/actions/workflows/release.yml)
[![Gateway Build](https://github.com/djkelleher/ib-docker/actions/workflows/build_gateway.yml/badge.svg)](https://github.com/djkelleher/ib-docker/actions/workflows/build_gateway.yml)
[![TWS Build](https://github.com/djkelleher/ib-docker/actions/workflows/build_tws.yml/badge.svg)](https://github.com/djkelleher/ib-docker/actions/workflows/build_tws.yml)


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
