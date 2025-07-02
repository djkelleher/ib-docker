# Interactive Brokers Gateway/TWS Docker

<p align="center">
  <img height="300" src="./.logo.jpg">
</p>

[![Daily Release Check](https://github.com/DankLabDev/ib-docker/actions/workflows/release.yml/badge.svg)](https://github.com/DankLabDev/ib-docker/actions/workflows/release.yml)
[![Gateway Build](https://github.com/DankLabDev/ib-docker/actions/workflows/build_gateway.yml/badge.svg)](https://github.com/DankLabDev/ib-docker/actions/workflows/build_gateway.yml)
[![TWS Build](https://github.com/DankLabDev/ib-docker/actions/workflows/build_tws.yml/badge.svg)](https://github.com/DankLabDev/ib-docker/actions/workflows/build_tws.yml)

Reliable, high-performance Docker images for running Interactive Brokers Gateway and TWS with full automation, SSH tunnel support, and robust process management.

## 🚀 Quick Start

**Images:** `danklabs/ib-gateway` • `danklabs/ib-tws`

VNC_PWD must be set, or VNC will not start.
`IB_USER` and `IB_PASSWORD`

### Supervisord Web Interface
Enable the web interface to monitor all processes:

```yaml
environment:
  SUPERVISORD_UI_PORT: 9001
  SUPERVISORD_UI_USER: admin    # Optional
  SUPERVISORD_UI_PASS: secret   # Optional
```

**Access:** `http://localhost:9001`


docker-compose exec ib-gateway supervisorctl status
### View live logs
docker-compose exec ib-gateway supervisorctl tail -f ibc

```bash
# 1. Get the project
git clone https://github.com/your-repo/ib-docker.git
cd ib-docker

# 2. Configure credentials
cp .env.example .env
# Edit .env with your IB username and password

# 3. Start container
docker-compose up -d

# 4. Connect your trading app to localhost:4002 (paper) or localhost:4001 (live)
```

## ✨ Features

- **🔄 Full Automation** - [IBC](https://github.com/IbcAlpha/IBC) handles login and session management
- **🖥️ Headless Operation** - [Xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml) virtual display + [x11vnc](https://wiki.archlinux.org/title/x11vnc) for remote GUI access
- **🔒 Secure Access** - SSH tunneling for encrypted remote API connections
- **📊 Process Management** - [Supervisord](http://supervisord.org/) with auto-recovery and web monitoring
- **🌐 Flexible Networking** - Host networking, bridge mode, or SSH-only configurations
- **📈 Production Ready** - Health checks, logging, and high-availability patterns

### Process Management with Supervisord
**Benefits:**
- Auto-recovery of failed processes
- Web interface at `http://localhost:9001` (optional)
- Independent logging for each service
- Proper startup dependencies

## Network Access Patterns
### When Socat is Needed
Socat forwards traffic from external-facing ports to internal IB Gateway ports.

| Scenario | Host Network | Bridge Network |
|----------|--------------|----------------|
| Local access only | Not needed | Not needed |
| External access | Optional | Required |
| Port mapping | Not needed | Required |

Understanding when you need socat vs SSH tunnels:

### ✅ **No Socat Needed** (`ENABLE_SOCAT=no`)
- Host networking + localhost access only
- SSH tunnels for remote access
- Single-machine deployments

### ✅ **Socat Required** (`ENABLE_SOCAT=yes`)
- External machine access without SSH
- Bridge networking mode
- Port mapping requirements

### Local Development
```yaml
services:
  ib-gateway:
    image: ib-gateway:latest
    network_mode: host
    environment:
      TRADING_MODE: paper
      ENABLE_SOCAT: "no"
      VNC_PWD: "password123"
```
**Access:** `localhost:4001` (paper: `localhost:4002`)

### 2. Remote Server with SSH Tunnel (Most Secure)
```yaml
services:
  ib-gateway:
    network_mode: host
    environment:
      ENABLE_SOCAT: "no"
      SSH_TUNNEL: "yes"
      SSH_USER_TUNNEL: "user@client-machine.com"
      SSH_REMOTE_PORT: "4001"
    volumes:
      - ~/.ssh:/home/ibuser/.ssh:ro
```
**Access:** `loaclhost:4001` (on client machine via tunnel)

### 3. External Network Access
```yaml
services:
  ib-gateway:
    network_mode: host
    environment:
      ENABLE_SOCAT: "yes"
      # Exposes API on ports 4003/4004 for external access
```
**Access:** `server-ip:4003` (paper: `server-ip:4004`)

### 4. Bridge Networking (Docker Standard)
```yaml
services:
  ib-gateway:
    ports:
      - "4001:4003"
      - "4002:4004"
      - "5900:5900"
    environment:
      ENABLE_SOCAT: "yes"  # Required for bridge mode
```
**Access:** `localhost:4001` (Docker port mapping)

## 🔐 Security Best Practices
1. **SSH Tunnels**: Use Ed25519 keys with strong passphrases
2. **Network Access**: Prefer `SSH_TUNNEL=yes` over external socat exposure
3. **Credentials**: Use `.env` files, never commit passwords
4. **VNC**: Set strong `VNC_PWD` if enabling VNC server
5. **Monitoring**: Enable supervisord web interface only on trusted networks
6. **Updates**: Regularly update container images and dependencies

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


| Service | Port | Description |
|---------|------|-------------|
| VNC | 5900 | Remote desktop access |
| Supervisord | 9001 | Process management web UI |

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

## Port Reference

| Program | Mode | Direct Port | Socat Port | Description |
|---------|------|-------------|------------|-------------|
| Gateway | Live | 4001 | 4003 | Live trading API |
| Gateway | Paper | 4002 | 4004 | Paper trading API |
| TWS | Live | 7496 | 7498 | Live trading API |
| TWS | Paper | 7497 | 7499 | Paper trading API |
| Both | - | 5900 | - | VNC server |

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
| `SUPERVISORD_UI_PORT` | - | Enable supervisord web interface on port |
| `SUPERVISORD_UI_USER` | - | Web interface username |
| `SUPERVISORD_UI_PASS` | - | Web interface password |

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | `1000` | User ID to run container as |
| `PGID` | `1000` | Group ID to run container as |
| `TZ` | `America/New_York` | Container timezone |
| `TRADING_MODE` | `paper` | Trading mode: `paper` or `live` |

| Variable | Effect | Use Case |
|----------|--------|----------|
| `ENABLE_SOCAT=no` | Disables port forwarding | Host networking + localhost-only |
| `SSH_TUNNEL=yes` | SSH tunnel only | Maximum security |
| `SSH_TUNNEL=both` | SSH + local access | Hybrid deployment |
| `SUPERVISORD_UI_PORT=9001` | Enable supervisord web UI | Process monitoring |

| Variable | Default | Description |
|----------|---------|-------------|
| `TRADING_MODE` | `paper` | Trading mode: `paper` or `live` |
| `ENABLE_SOCAT` | `yes` | Enable port forwarding (required for bridge networking) |
| `SSH_TUNNEL` | - | SSH tunnel mode: `yes`, `both`, or empty |
| `SSH_USER_TUNNEL` | - | SSH connection string (user@host) |
| `VNC_PWD` | - | VNC server password (enables VNC if set) |
| `SUPERVISORD_UI_PORT` | - | Enable supervisord web interface on port |
| `AUTO_RESTART_TIME` | - | Daily restart time (HH:MM AM/PM) |

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
| `SUPERVISORD_UI_PORT` | - | Enable supervisord web interface on port |
| `SUPERVISORD_UI_USER` | - | Web interface username |
| `SUPERVISORD_UI_PASS` | - | Web interface password |

## 🔌 API Access

| Program | Mode | Port | Description |
|---------|------|------|-------------|
| Gateway | Live | 4001 | Live trading API |
| Gateway | Paper | 4002 | Paper trading API |
| TWS | Live | 7496 | Live trading API |
| TWS | Paper | 7497 | Paper trading API |



### JVM Tuning

```bash
# Custom Java options
JAVA_OPTS="-Xmx2g -Xms1g -XX:+UseG1GC"
```


# Network Architecture Guide

This guide explains the networking concepts and configurations available in the IB Docker container.

## Overview

The container supports multiple networking patterns to accommodate different deployment scenarios:

1. **Host Networking** - Direct access to host network stack
2. **Bridge Networking** - Isolated container network with port forwarding
3. **SSH Tunneling** - Secure remote access through encrypted tunnels

## Host Networking Mode

### Configuration

```yaml
services:
  ib-gateway:
    network_mode: host
    environment:
      ENABLE_SOCAT: "no"
```

### How It Works

```
┌─────────────────────────────────────────┐
│ Host Machine                            │
│ ┌─────────────────────────────────────┐ │
│ │ Container (host network)            │ │
│ │ ┌─────────────┐                     │ │
│ │ │ IB Gateway  │ ──── localhost:4001 │ │
│ │ │             │ ──── localhost:4002 │ │
│ │ └─────────────┘                     │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### Advantages
- **Direct Access**: No port mapping needed
- **Performance**: Minimal network overhead
- **Simplicity**: Straightforward configuration

### Disadvantages
- **Port Conflicts**: Must avoid conflicting services on host
- **Security**: Less network isolation

### Use Cases
- Development environments
- Single-application servers
- When maximum performance is needed

## Bridge Networking Mode

### Configuration

```yaml
services:
  ib-gateway:
    ports:
      - "4001:4003"  # Live API
      - "4002:4004"  # Paper API
      - "5900:5900"  # VNC
    environment:
      ENABLE_SOCAT: "yes"
```

### How It Works

```
┌─────────────────────────────────────────┐
│ Host Machine                            │
│                                         │
│ localhost:4001 ────┐                    │
│ localhost:4002 ────┼────┐               │
│                    │    │               │
│ ┌──────────────────▼────▼─────────────┐ │
│ │ Container (bridge network)          │ │
│ │ ┌─────────────┐  ┌─────────────────┐│ │
│ │ │ IB Gateway  │──│ socat forwarder ││ │
│ │ │ :4001/:4002 │  │ :4003/:4004     ││ │
│ │ └─────────────┘  └─────────────────┘│ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### Advantages
- **Isolation**: Better container security
- **Flexibility**: Easy port remapping
- **Standard**: Uses Docker's default networking

### Disadvantages
- **Complexity**: Requires socat for external access
- **Performance**: Additional network layer

### Use Cases
- Production deployments
- Multi-container environments
- When network isolation is required

## SSH Tunneling

### Configuration Modes

#### SSH Only (`SSH_TUNNEL=yes`)
```yaml
environment:
  SSH_TUNNEL: "yes"
  SSH_USER_TUNNEL: "user@client.example.com"
  ENABLE_SOCAT: "no"
```

# SSH Tunnel Setup Guide

This comprehensive guide covers setting up SSH tunneling for secure remote access to your IB Gateway/TWS container.

## Overview
SSH tunneling provides secure, encrypted access to your IB Gateway API from remote locations. This is the recommended approach for production deployments where security is paramount.

### How SSH Tunneling Works

```
┌─────────────────────┐    SSH Tunnel    ┌─────────────────────┐
│ Client Machine      │ ◄──────────────► │ Server (Container)  │
│                     │                  │                     │
│ Trading App ────────┼──────────────────┼───► IB Gateway      │
│ localhost:4001      │                  │     :4001           │
│                     │                  │                     │
└─────────────────────┘                  └─────────────────────┘
```

The container establishes a reverse SSH tunnel to your client machine, making the API accessible via localhost on the client.

## Prerequisites

## Step 1: Generate SSH Keys

### On the Client Machine

Generate a dedicated SSH key pair for the IB Gateway tunnel:

```bash
# Generate Ed25519 key (recommended)
ssh-keygen -t ed25519 -f ~/.ssh/ib_tunnel -C "ib-gateway-tunnel"

# Or RSA if Ed25519 is not supported
ssh-keygen -t rsa -b 4096 -f ~/.ssh/ib_tunnel -C "ib-gateway-tunnel"

# Set proper permissions
chmod 600 ~/.ssh/ib_tunnel
chmod 644 ~/.ssh/ib_tunnel.pub
```

### Key Management Best Practices

```bash
# Use a strong passphrase
ssh-keygen -t ed25519 -f ~/.ssh/ib_tunnel -N "your-strong-passphrase"

# Add to SSH agent for convenience
ssh-add ~/.ssh/ib_tunnel

# Create SSH config for easy access
cat >> ~/.ssh/config << EOF
Host ib-server
    HostName your-server.com
    User your-username
    IdentityFile ~/.ssh/ib_tunnel
    IdentitiesOnly yes
EOF
```


## Step 4: SSH Configuration Options

### Container SSH Configuration

Create a custom SSH config file for the container:

```bash
# Create ssh_config file
cat > ssh_config << EOF
Host *
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR
    ServerAliveInterval 30
    ServerAliveCountMax 3
    ExitOnForwardFailure yes
    TCPKeepAlive yes
EOF
```

### Advanced SSH Options

| Option | Description | Example |
|--------|-------------|---------|
| `SSH_OPTIONS` | Additional SSH command options | `-o ConnectTimeout=10` |
| `SSH_ALIVE_INTERVAL` | Keep-alive interval (seconds) | `20` |
| `SSH_ALIVE_COUNT` | Keep-alive retry count | `3` |
| `SSH_RESTART` | Restart delay after failure | `5` |


## Security Considerations

### Key Management

```bash
# Use strong passphrases
ssh-keygen -t ed25519 -f ~/.ssh/ib_tunnel -N "$(openssl rand -base64 32)"

# Restrict key usage
echo 'command="/bin/false",no-pty,no-X11-forwarding,permitopen="localhost:4001" ssh-ed25519 AAAA...' >> ~/.ssh/authorized_keys

# Regular key rotation
ssh-keygen -t ed25519 -f ~/.ssh/ib_tunnel_new
# ... update configuration and remove old key
```

### Network Security

```bash
# Bind to localhost only on client
SSH_REMOTE_PORT=127.0.0.1:4001

# Use non-standard SSH port
SSH_USER_TUNNEL=user@client-machine.com:2222

# Restrict SSH access by IP
# In client's /etc/ssh/sshd_config:
# AllowUsers user@server-ip-address
```


## Advanced Configurations

### Multiple Tunnels

```yaml
# Multiple API endpoints
environment:
  SSH_TUNNEL: "both"  # Enable SSH + local access
  SSH_USER_TUNNEL: "user1@client1.com,user2@client2.com"
  SSH_REMOTE_PORT: "4001,4002"
```



### SSH Bastion Host

```yaml
# Route through bastion host
environment:
  SSH_OPTIONS: "-o ProxyCommand='ssh bastion nc %h %p'"
  SSH_USER_TUNNEL: "user@internal-client"
```


## Tunnel Modes

### SSH Only (`SSH_TUNNEL=yes`)
- Most secure option
- Only SSH tunnel, no local port forwarding
- Access only through remote server

### Hybrid Mode (`SSH_TUNNEL=both`)
- SSH tunnel + local socat
- Allows both local and remote access
- Good for development/testing

### Traditional Mode (`SSH_TUNNEL=` empty)
- No SSH tunnel
- Only local socat port forwarding
- Default behavior

### Tunnel Keeps Disconnecting
- Increase `SSH_ALIVE_INTERVAL` and `SSH_ALIVE_COUNT`
- Check network stability
- Verify SSH server configuration allows keep-alive

### Basic SSH Tunnel
```bash
SSH_TUNNEL=yes
SSH_USER_TUNNEL=trader@vps.example.com
```

### Advanced SSH Tunnel with Custom Options
```bash
SSH_TUNNEL=both
SSH_USER_TUNNEL=trader@vps.example.com
SSH_REMOTE_PORT=14001
SSH_VNC_PORT=15900
SSH_OPTIONS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
SSH_ALIVE_INTERVAL=30
SSH_ALIVE_COUNT=5
```

### Optimize SSH Settings
```bash
# In ssh_config or SSH_OPTIONS
Compression yes
TCPKeepAlive yes
ServerAliveInterval 30
ServerAliveCountMax 3
```
