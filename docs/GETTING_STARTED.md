# Getting Started with IB Docker

This guide will help you quickly set up and run Interactive Brokers Gateway or TWS using Docker.

## Prerequisites

- Docker and Docker Compose installed
- Interactive Brokers account
- Basic understanding of Docker concepts

## Quick Start

### 1. Download the Project

```bash
git clone https://github.com/your-repo/ib-docker.git
cd ib-docker
```

### 2. Configure Environment

Copy the example environment file and customize it:

```bash
cp .env.example .env
```

Edit `.env` with your IB credentials:

```bash
# Required: Interactive Brokers credentials
IB_USER=your_username
IB_PASSWORD=your_password

# Optional: Trading mode (paper or live)
TRADING_MODE=paper

# Optional: VNC password for GUI access
VNC_PWD=your_vnc_password
```

### 3. Start the Container

Choose your preferred method:

#### Option A: Gateway (Recommended for API-only usage)
```bash
# Edit docker-compose.yml to use ibgateway
docker-compose up -d
```

#### Option B: TWS (Full Trading Workstation)
```bash
# Edit docker-compose.yml to use tws
docker-compose up -d
```

### 4. Verify Installation

Check that services are running:

```bash
# Run the test script
./tests/test_ssh_tunnel.sh

# Or check manually
docker-compose ps
docker-compose logs ib-gateway
```

### 5. Connect to API

Once running, connect your trading application to:

- **Paper Trading**: `localhost:4002` (Gateway) or `localhost:7497` (TWS)
- **Live Trading**: `localhost:4001` (Gateway) or `localhost:7496` (TWS)

## What's Next?

- **GUI Access**: Connect to VNC at `localhost:5900` if VNC_PWD is set
- **Remote Access**: See [SSH Setup Guide](./SSH_SETUP.md) for secure remote connections
- **Advanced Config**: Check [Configuration Guide](./CONFIGURATION.md) for detailed options
- **Troubleshooting**: See [Troubleshooting Guide](./TROUBLESHOOTING.md) if you encounter issues

## Common First Steps

### Enable VNC for GUI Access

Add to your `.env` file:
```bash
VNC_PWD=your_secure_password
```

Then connect with any VNC client to `localhost:5900`.

### Test API Connection

```bash
# Test with telnet
telnet localhost 4002

# Or use curl to check if port is open
curl -v telnet://localhost:4002
```

### View Live Logs

```bash
# All container logs
docker-compose logs -f

# Specific service logs
docker-compose exec ib-gateway supervisorctl tail -f ibc
```

## Architecture Overview

The container runs several services managed by supervisord:

```
├── Xvfb (Virtual Display)
├── IBC (Gateway/TWS Controller)
├── x11vnc (VNC Server) [Optional]
├── socat (Port Forwarding) [Conditional]
└── ssh-tunnel (SSH Tunneling) [Optional]
```

Each service is independently monitored and restarted automatically if it fails.
