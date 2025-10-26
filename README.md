# Interactive Brokers Gateway/TWS Docker

<p align="center">
  <img height="300" src="./.logo.jpg">
</p>

[![Daily Release Check](https://github.com/djkelleher/ib-docker/actions/workflows/release.yml/badge.svg)](https://github.com/djkelleher/ib-docker/actions/workflows/release.yml)
[![Gateway Build](https://github.com/djkelleher/ib-docker/actions/workflows/build_gateway.yml/badge.svg)](https://github.com/djkelleher/ib-docker/actions/workflows/build_gateway.yml)
[![TWS Build](https://github.com/djkelleher/ib-docker/actions/workflows/build_tws.yml/badge.svg)](https://github.com/djkelleher/ib-docker/actions/workflows/build_tws.yml)

Reliable, high-performance Docker images for running Interactive Brokers Gateway and TWS with full automation and robust process management.

## 🚀 Quick Start

**Images:** `danklabs/ib-gateway` • `danklabs/ib-tws`

VNC_PWD must be set, or VNC will not start. `IB_USER` and `IB_PASSWORD` must be provided.

```bash
# 1. Get the project
git clone https://github.com/djkelleher/ib-docker.git
cd ib-docker

# 2. Configure credentials
cp .env.example .env
# Edit .env with your IB username and password

# 3. Start container
docker compose up -d

# 4. Connect your trading app to localhost:4002 (paper) or localhost:4001 (live)
```

### Supervisord Web Interface
Enable the web interface to monitor all processes:

```yaml
environment:
  SUPERVISORD_UI_PORT: 9001
  SUPERVISORD_UI_USER: admin    # Optional
  SUPERVISORD_UI_PASS: secret   # Optional
```

**Access:** `http://localhost:9001`

View process status & logs:
```bash
docker compose exec ib-gateway supervisorctl status
docker compose exec ib-gateway supervisorctl tail -f ibc
```

## ✨ Features

- **🔄 Full Automation** - [IBC](https://github.com/IbcAlpha/IBC) handles login and session management
- **🖥️ Headless Operation** - [Xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml) virtual display + [x11vnc](https://wiki.archlinux.org/title/x11vnc) for remote GUI access
- **📊 Process Management** - [Supervisord](http://supervisord.org/) with auto-recovery and web monitoring
- **🌐 Flexible Networking** - Host networking or bridge mode configurations
- **📈 Production Ready** - Health checks, logging, and high-availability patterns
- **🐳 Multi-stage Build** - All install logic embedded in `build/Dockerfile` (legacy `install.sh` removed)

### Process Management with Supervisord
**Benefits:**
- Auto-recovery of failed processes
- Web interface at `http://localhost:9001` (optional)
- Independent logging for each service
- Proper startup dependencies

## 🔧 Building Locally

```bash
# Build gateway (stable)
docker build -t danklabs/ib-gateway:stable \
  --build-arg PROGRAM=ibgateway --build-arg RELEASE=stable build/

# Build TWS (stable)
docker build -t danklabs/ib-tws:stable \
  --build-arg PROGRAM=tws --build-arg RELEASE=stable build/
```

Optional build args:
| ARG | Values | Purpose |
|-----|--------|---------|
| PROGRAM | ibgateway, tws | Select which app to install |
| RELEASE | stable, latest, beta | IB upstream release channel |
| VERSION | NULL or numeric | Specific packaged version (internal use) |
| IBC_VERSION | e.g. 3.23.0 | IBC release to bundle |

## Network Access Patterns

| Scenario | Host Network | Bridge Network |
|----------|--------------|----------------|
| Local access only | Direct access | Port mapping |
| External access | Direct access | Port mapping |

### Host Networking (Simple / Fast)
```yaml
services:
  ib-gateway:
    image: danklabs/ib-gateway:stable
    network_mode: host
    environment:
      TRADING_MODE: paper
```
**Access:** `localhost:4001` (paper: `localhost:4002`)

### Bridge Networking (Isolated)
```yaml
services:
  ib-gateway:
    image: danklabs/ib-gateway:stable
    ports:
      - "4001:4001"
      - "4002:4002"
      - "5900:5900"
    environment:
      TRADING_MODE: paper
```

## 🔐 Security Best Practices
1. **Credentials**: Use `.env` files, never commit passwords
2. **VNC**: Set strong `VNC_PWD` if enabling VNC server
3. **Monitoring**: Enable supervisord web interface only on trusted networks
4. **Updates**: Regularly update container images and dependencies

# Configuration Guide

## Environment Variables Reference

### Basic Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | `1000` | User ID to run container as |
| `PGID` | `1000` | Group ID to run container as |
| `TZ` | `America/New_York` | Container timezone |
| `TRADING_MODE` | `paper` | Trading mode: `paper` or `live` |
| `ACCEPT_NON_BROKERAGE_WARNING` | `yes` | Auto-accept paper trading account warning dialog |

### IB Credentials
| Variable | Required | Description |
|----------|----------|-------------|
| `IB_USER` | Yes | Interactive Brokers username |
| `IB_PASSWORD` | Yes | Interactive Brokers password |

### Display & VNC
| Variable | Default | Description |
|----------|---------|-------------|
| `VNC_PWD` | - | VNC server password (enables VNC if set) |
| `VNC_SCREEN_DIMENSION` | `1600x1200x16` | VNC screen resolution |
| `DISPLAY` | `:0` | X11 display number |

### IBC Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| `READ_ONLY_API` | `no` | Enable read-only API mode |
| `TWOFA_TIMEOUT_ACTION` | `exit` | Action on 2FA timeout: `exit` or `restart` |
| `AUTO_RESTART_TIME` | - | Daily restart time (HH:MM AM/PM) |
| `AUTO_LOGOFF_TIME` | - | Daily logoff time (HH:MM AM/PM) |
| `COLD_RESTART_TIME` | - | Sunday cold restart time |
| `BYPASS_WARNING` | `yes` | Bypass API warning dialogs |
| `SAVE_TWS_SETTINGS` | `Every 30 mins` | TWS settings save schedule |
| `RELOGIN_AFTER_TWOFA_TIMEOUT` | `no` | Auto-relogin after 2FA timeout |
| `TWOFA_EXIT_INTERVAL` | `60` | 2FA timeout interval (seconds) |

### Supervisord Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| `SUPERVISORD_UI_PORT` | - | Enable supervisord web interface on port |
| `SUPERVISORD_UI_USER` | - | Web interface username |
| `SUPERVISORD_UI_PASS` | - | Web interface password |

### Ports
| Service | Port | Description |
|---------|------|-------------|
| Gateway Live | 4001 | Live trading API |
| Gateway Paper | 4002 | Paper trading API |
| TWS Live | 7496 | Live trading API |
| TWS Paper | 7497 | Paper trading API |
| VNC | 5900 | Remote desktop access |
| Supervisord UI | 9001 | Process management web UI (optional) |

## 🔌 API Access (Summary)
Same as Ports table above. Map or expose as required.

### JVM Tuning
```bash
# Example custom Java options
JAVA_OPTS="-Xmx2g -Xms1g -XX:+UseG1GC"
```

## Network Architecture Guide

The container supports two main networking patterns: **host** and **bridge** (shown above). Choose based on isolation vs simplicity.

## 🗑️ Legacy Cleanup Note
The historical `build/install.sh` helper script has been removed. All install logic is now implemented directly inside the multi-stage `build/Dockerfile` (builder stage). This reduces duplication and ensures reproducible builds.

## 📄 License
MIT

## 🙌 Contributions
Issues and PRs welcome. Please open an issue for feature discussions first.
