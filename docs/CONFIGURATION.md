# Configuration Guide

This guide covers all configuration options available for the IB Docker container.

## Environment Variables Reference

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | `1000` | User ID to run container as |
| `PGID` | `1000` | Group ID to run container as |
| `TZ` | `America/New_York` | Container timezone |
| `TRADING_MODE` | `paper` | Trading mode: `paper` or `live` |

### IB Credentials

| Variable | Required | Description |
|----------|----------|-------------|
| `IB_USER` | Yes | Interactive Brokers username |
| `IB_PASSWORD` | Yes | Interactive Brokers password |

### Display and VNC

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

### Network Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_SOCAT` | `yes` | Enable port forwarding via socat |

### SSH Tunnel Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SSH_TUNNEL` | - | SSH tunnel mode: `yes`, `both`, or empty |
| `SSH_USER_TUNNEL` | - | SSH connection string (user@host) |
| `SSH_REMOTE_PORT` | - | Remote port to expose |
| `SSH_VNC_PORT` | - | Remote VNC port (optional) |
| `SSH_RDP_PORT` | - | Remote RDP port (optional) |
| `SSH_PASSPHRASE` | - | SSH key passphrase |
| `SSH_PASSPHRASE_FILE` | - | Path to file containing SSH passphrase |
| `SSH_OPTIONS` | - | Additional SSH options |
| `SSH_ALIVE_INTERVAL` | `20` | SSH keep-alive interval |
| `SSH_ALIVE_COUNT` | `3` | SSH keep-alive count |
| `SSH_RESTART` | `5` | SSH restart delay (seconds) |

### Supervisord Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTP_SERVER_PORT` | - | Enable supervisord web interface on port |
| `HTTP_SERVER_USER` | - | Web interface username |
| `HTTP_SERVER_PASS` | - | Web interface password |

## Network Modes

### Host Networking (Recommended)

```yaml
services:
  ib-gateway:
    network_mode: host
    environment:
      ENABLE_SOCAT: "no"  # Not needed with host networking
```

**Pros:**
- Simplest configuration
- Direct port access
- Best performance

**Cons:**
- Less isolation
- Potential port conflicts

### Bridge Networking

```yaml
services:
  ib-gateway:
    ports:
      - "4001:4003"  # Live API
      - "4002:4004"  # Paper API
      - "5900:5900"  # VNC
    environment:
      ENABLE_SOCAT: "yes"  # Required for external access
```

**Pros:**
- Better isolation
- Flexible port mapping
- Standard Docker approach

**Cons:**
- Requires socat for external access
- More complex configuration

## Port Mappings

### Gateway Ports

| Mode | Internal Port | Socat Port | Description |
|------|---------------|------------|-------------|
| Live | 4001 | 4003 | Live trading API |
| Paper | 4002 | 4004 | Paper trading API |

### TWS Ports

| Mode | Internal Port | Socat Port | Description |
|------|---------------|------------|-------------|
| Live | 7496 | 7498 | Live trading API |
| Paper | 7497 | 7499 | Paper trading API |

### Other Services

| Service | Port | Description |
|---------|------|-------------|
| VNC | 5900 | VNC remote desktop |
| Supervisord | 9001 | Web management interface |

## Volume Mounts

### SSH Keys
```yaml
volumes:
  - ~/.ssh:/home/ibuser/.ssh:ro
```

Mount SSH keys for tunnel authentication.

### Custom Configuration
```yaml
volumes:
  - ./custom-ibc.ini:/opt/ibc/ibc.ini
  - ./custom-jts.ini:/opt/ibgateway/stable/jts.ini
```

Override default IBC and TWS configuration.

### Persistent Settings
```yaml
volumes:
  - ./tws_settings:/home/ibuser/tws_settings
```

Preserve TWS settings between container restarts.

## Configuration Files

### IBC Configuration

Location: `/opt/ibc/ibc.ini`

Key settings you might want to customize:

```ini
# Login settings
IbLoginId=your_username
IbPassword=your_password
TradingMode=paper

# API settings
IbApiLogging=yes
ApiPortNumber=4001

# Timezone
IbConnectionTimeZone=America/New_York

# Auto-restart settings
ClosedownAt=
AutoRestartTime=
```

Use [config/ibc.empty.ini](../config/ibc.empty.ini) as a template.

### TWS/Gateway Configuration

Locations:
- Gateway Stable: `/opt/ibgateway/stable/jts.ini`
- Gateway Latest: `/opt/ibgateway/latest/jts.ini`
- TWS Stable: `/Jts/stable/jts.ini`
- TWS Latest: `/Jts/latest/jts.ini`

## Example Configurations

### Development Setup
```yaml
services:
  ib-gateway:
    image: ib-gateway:latest
    network_mode: host
    environment:
      TRADING_MODE: paper
      VNC_PWD: devpassword
      ENABLE_SOCAT: "no"
```

### Production with SSH Tunnel
```yaml
services:
  ib-gateway:
    image: ib-gateway:latest
    network_mode: host
    environment:
      TRADING_MODE: live
      SSH_TUNNEL: "yes"
      SSH_USER_TUNNEL: "trader@client.example.com"
      ENABLE_SOCAT: "no"
    volumes:
      - ~/.ssh:/home/ibuser/.ssh:ro
```

### High Availability Setup
```yaml
services:
  ib-gateway:
    image: ib-gateway:latest
    restart: always
    network_mode: host
    environment:
      AUTO_RESTART_TIME: "23:55 PM"
      RELOGIN_AFTER_TWOFA_TIMEOUT: "yes"
      HTTP_SERVER_PORT: 9001
      SAVE_TWS_SETTINGS: "Every 15 mins"
```

## Environment File Template

Create a `.env` file with these settings:

```bash
# === Required Settings ===
IB_USER=your_username
IB_PASSWORD=your_password

# === Basic Configuration ===
TRADING_MODE=paper
TIME_ZONE=America/New_York

# === Optional: VNC Access ===
VNC_PWD=your_vnc_password

# === Optional: SSH Tunnel ===
SSH_TUNNEL=
SSH_USER_TUNNEL=
SSH_REMOTE_PORT=

# === Advanced Settings ===
AUTO_RESTART_TIME=
READ_ONLY_API=no
ENABLE_SOCAT=yes

# === Monitoring ===
HTTP_SERVER_PORT=
HTTP_SERVER_USER=
HTTP_SERVER_PASS=
```
