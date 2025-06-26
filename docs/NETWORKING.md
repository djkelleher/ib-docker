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

#### SSH + Local (`SSH_TUNNEL=both`)
```yaml
environment:
  SSH_TUNNEL: "both"
  SSH_USER_TUNNEL: "user@client.example.com"
  ENABLE_SOCAT: "yes"
```

### How SSH Tunneling Works

```
┌─────────────────────┐    SSH Tunnel    ┌─────────────────────┐
│ Client Machine      │ ◄──────────────► │ Server (Container)  │
│                     │                  │                     │
│ localhost:4001 ─────┼──────────────────┼───► IB Gateway:4001 │
│ localhost:4002 ─────┼──────────────────┼───► IB Gateway:4002 │
│                     │                  │                     │
│ Trading App         │                  │ Docker Container    │
└─────────────────────┘                  └─────────────────────┘
```

### SSH Tunnel Process

1. **Container starts SSH client**
2. **Connects to remote client machine**
3. **Creates reverse tunnel** (server → client)
4. **Client accesses API** via localhost

### Advantages
- **Security**: Encrypted connection
- **Firewall Friendly**: Only SSH port needed
- **Authentication**: SSH key-based security

### Disadvantages
- **Complexity**: SSH key management required
- **Dependencies**: Requires SSH access to client
- **Latency**: Additional network hop

## Port Reference

### Gateway Ports

| Service | Mode | Internal | Socat | Description |
|---------|------|----------|-------|-------------|
| API | Live | 4001 | 4003 | Live trading API |
| API | Paper | 4002 | 4004 | Paper trading API |

### TWS Ports

| Service | Mode | Internal | Socat | Description |
|---------|------|----------|-------|-------------|
| API | Live | 7496 | 7498 | Live trading API |
| API | Paper | 7497 | 7499 | Paper trading API |

### Auxiliary Services

| Service | Port | Description |
|---------|------|-------------|
| VNC | 5900 | Remote desktop access |
| Supervisord | 9001 | Process management web UI |

## Socat Port Forwarding

### Purpose
Socat forwards traffic from external-facing ports to internal IB Gateway ports.

### Configuration
Enabled when `ENABLE_SOCAT=yes`:

```bash
# Gateway forwarding
socat TCP-LISTEN:4003,fork,reuseaddr TCP:localhost:4001
socat TCP-LISTEN:4004,fork,reuseaddr TCP:localhost:4002

# TWS forwarding
socat TCP-LISTEN:7498,fork,reuseaddr TCP:localhost:7496
socat TCP-LISTEN:7499,fork,reuseaddr TCP:localhost:7497
```

### When Socat is Needed

| Scenario | Host Network | Bridge Network |
|----------|--------------|----------------|
| Local access only | Not needed | Not needed |
| External access | Optional | Required |
| Port mapping | Not needed | Required |

## Network Troubleshooting

### Check Port Accessibility

```bash
# Test internal ports (in container)
docker-compose exec ib-gateway netstat -tlnp | grep -E "(4001|4002)"

# Test external ports (from host)
telnet localhost 4001
nc -zv localhost 4002

# Test socat forwarding
docker-compose exec ib-gateway netstat -tlnp | grep -E "(4003|4004)"
```

### Verify SSH Tunnels

```bash
# Check SSH process in container
docker-compose exec ib-gateway pgrep ssh

# Check tunnel from client machine
ssh user@server.com "netstat -tlnp | grep 4001"

# Test connection from client
telnet localhost 4001
```

### Debug Network Issues

```bash
# Check container networking mode
docker inspect <container_id> | grep NetworkMode

# Check port bindings
docker port <container_name>

# Check process listening on ports
docker-compose exec ib-gateway netstat -tlnp
```

## Security Considerations

### Host Networking
- **Exposure**: All container ports accessible on host
- **Firewall**: Host firewall applies
- **Mitigation**: Use SSH tunnels for remote access

### Bridge Networking
- **Isolation**: Container network isolated
- **Exposure**: Only mapped ports accessible
- **Firewall**: Docker manages iptables rules

### SSH Tunneling
- **Encryption**: All traffic encrypted
- **Authentication**: SSH key-based
- **Authorization**: Client machine access required

## Best Practices

### For Development
```yaml
# Simple local setup
network_mode: host
environment:
  ENABLE_SOCAT: "no"
  VNC_PWD: "development"
```

### For Production
```yaml
# Secure remote access
network_mode: host
environment:
  SSH_TUNNEL: "yes"
  SSH_USER_TUNNEL: "trader@secure-client.com"
  ENABLE_SOCAT: "no"
volumes:
  - ~/.ssh:/home/ibuser/.ssh:ro
```

### For Multi-Service Environments
```yaml
# Isolated with specific port exposure
ports:
  - "127.0.0.1:4001:4003"  # Bind to localhost only
environment:
  ENABLE_SOCAT: "yes"
```

## Performance Optimization

### Reduce Network Latency
- Use host networking when possible
- Disable unnecessary services
- Use local storage for configuration

### Monitor Network Usage
```bash
# Check network statistics
docker stats ib-gateway

# Monitor specific ports
ss -tulpn | grep -E "(4001|4002)"

# Check connection counts
netstat -ant | grep -E "(4001|4002)" | wc -l
```
