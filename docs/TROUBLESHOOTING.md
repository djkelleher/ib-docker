# Troubleshooting Guide

This guide helps you diagnose and fix common issues with the IB Docker container.

## Quick Diagnostics

### Check Container Status
```bash
# Check if container is running
docker-compose ps

# Check container logs
docker-compose logs ib-gateway

# Check specific service logs
docker-compose exec ib-gateway supervisorctl status
```

### Run Automated Tests
```bash
# Run the comprehensive test script
./tests/test_ssh_tunnel.sh

# Check port accessibility
netstat -tlnp | grep -E ':(4001|4002|4003|4004|7496|7497|7498|7499)'
```

## Common Issues

### 1. Container Won't Start

**Symptoms:**
- Container exits immediately
- Error messages in `docker-compose logs`

**Diagnosis:**
```bash
# Check for configuration errors
docker-compose config

# Check environment file
cat .env

# Check for missing required variables
docker-compose exec ib-gateway env | grep -E "(IB_USER|IB_PASSWORD)"
```

**Solutions:**
- Verify `.env` file exists and contains `IB_USER` and `IB_PASSWORD`
- Check for syntax errors in `docker-compose.yml`
- Ensure proper file permissions: `chmod 600 .env`

### 2. API Connection Refused

**Symptoms:**
- `Connection refused` when trying to connect to API ports
- Trading applications can't connect

**Diagnosis:**
```bash
# Check if IBC is running
docker-compose exec ib-gateway pgrep java

# Check API ports
docker-compose exec ib-gateway netstat -tlnp | grep -E "(4001|4002|7496|7497)"

# Test local connection
telnet localhost 4002
```

**Solutions:**

#### If using host networking:
```bash
# Check if socat is needed
docker-compose exec ib-gateway pgrep socat

# If no socat and external access needed, enable it:
# Add to .env: ENABLE_SOCAT=yes
```

#### If using bridge networking:
```bash
# Ensure socat is enabled
# Add to .env: ENABLE_SOCAT=yes

# Check port mappings in docker-compose.yml
```

### 3. SSH Tunnel Not Working

**Symptoms:**
- SSH connection fails
- `ssh` process not running in container

**Diagnosis:**
```bash
# Check SSH process
docker-compose exec ib-gateway pgrep ssh

# Check SSH configuration
docker-compose exec ib-gateway env | grep SSH

# Test SSH connection manually
docker-compose exec ib-gateway ssh -T user@server.com
```

**Solutions:**

#### SSH Keys Not Mounted:
```yaml
volumes:
  - ~/.ssh:/home/ibuser/.ssh:ro
```

#### SSH Key Permissions:
```bash
# Fix permissions on host
chmod 600 ~/.ssh/id_*
chmod 644 ~/.ssh/id_*.pub
chmod 700 ~/.ssh
```

#### SSH Agent Issues:
```bash
# Check if passphrase is needed
docker-compose exec ib-gateway ssh-add -l

# Add passphrase to .env if needed
SSH_PASSPHRASE=your_passphrase
```

### 4. VNC Connection Issues

**Symptoms:**
- Can't connect to VNC
- Black screen in VNC viewer

**Diagnosis:**
```bash
# Check if VNC server is running
docker-compose exec ib-gateway pgrep x11vnc

# Check if Xvfb is running
docker-compose exec ib-gateway pgrep Xvfb

# Check VNC password is set
docker-compose exec ib-gateway env | grep VNC_PWD
```

**Solutions:**
- Ensure `VNC_PWD` is set in environment
- Check firewall settings
- Try different VNC clients

### 5. IBC/TWS Login Issues

**Symptoms:**
- Login window appears but doesn't auto-login
- "Invalid credentials" messages
- TWS/Gateway keeps restarting

**Diagnosis:**
```bash
# Check IBC logs
docker-compose exec ib-gateway supervisorctl tail -f ibc

# Check credentials are set
docker-compose exec ib-gateway env | grep -E "(IB_USER|IB_PASSWORD)"

# Check IBC configuration
docker-compose exec ib-gateway cat /opt/ibc/ibc.ini | grep -E "(LoginId|Password|TradingMode)"
```

**Solutions:**
- Verify IB credentials are correct
- Check if 2FA is required and configure accordingly
- Ensure trading mode matches account type
- Check for account restrictions

### 6. Process Keeps Crashing

**Symptoms:**
- Services frequently restart
- Supervisord shows failed processes

**Diagnosis:**
```bash
# Check supervisord status
docker-compose exec ib-gateway supervisorctl status

# Check system resources
docker stats ib-gateway

# Check individual service logs
docker-compose exec ib-gateway supervisorctl tail ssh-tunnel
docker-compose exec ib-gateway supervisorctl tail ibc
```

**Solutions:**
- Increase container memory limits
- Check disk space
- Review service-specific logs for errors

## Service-Specific Troubleshooting

### Supervisord Web Interface

If the web interface isn't accessible:

```bash
# Check if HTTP server is enabled
docker-compose exec ib-gateway env | grep HTTP_SERVER_PORT

# Check if service is running
docker-compose exec ib-gateway netstat -tlnp | grep 9001
```

Enable in `.env`:
```bash
HTTP_SERVER_PORT=9001
HTTP_SERVER_USER=admin
HTTP_SERVER_PASS=password
```

### Socat Port Forwarding

If external connections fail:

```bash
# Check socat processes
docker-compose exec ib-gateway pgrep socat

# Check socat configuration
docker-compose exec ib-gateway ps aux | grep socat
```

## Advanced Debugging

### Enable Debug Logging

Add to `.env`:
```bash
IBC_DEBUG=yes
SSH_DEBUG=yes
```

### Container Shell Access

```bash
# Get shell access
docker-compose exec ib-gateway bash

# Check running processes
ps aux

# Check network configuration
ip addr show
netstat -tlnp
```

### Manual Service Control

```bash
# Restart specific services
docker-compose exec ib-gateway supervisorctl restart ibc
docker-compose exec ib-gateway supervisorctl restart ssh-tunnel

# Stop/start services
docker-compose exec ib-gateway supervisorctl stop socat
docker-compose exec ib-gateway supervisorctl start socat
```

## Performance Issues

### High CPU Usage

```bash
# Check process CPU usage
docker-compose exec ib-gateway top

# Check Java heap usage
docker-compose exec ib-gateway jstat -gc $(pgrep java)
```

### Memory Issues

```bash
# Check memory usage
docker stats ib-gateway

# Check Java memory
docker-compose exec ib-gateway jstat -gc $(pgrep java)
```

## Network Debugging

### Port Connectivity

```bash
# Test specific ports
telnet localhost 4001
nc -zv localhost 4002

# Check what's listening
netstat -tlnp | grep -E "(4001|4002|4003|4004)"
```

### SSH Tunnel Testing

```bash
# Test tunnel from remote machine
ssh -L 4001:localhost:4001 user@server.com

# Check tunnel status
docker-compose exec ib-gateway netstat -tlnp | grep ssh
```

## Getting Help

### Collect Debug Information

```bash
# System information
docker --version
docker-compose --version

# Container configuration
docker-compose config

# Service status
docker-compose exec ib-gateway supervisorctl status

# Recent logs
docker-compose logs --tail=50 ib-gateway

# Environment variables (sanitized)
docker-compose exec ib-gateway env | grep -v PASSWORD
```

### Log Locations

- **Container logs**: `docker-compose logs ib-gateway`
- **Supervisord logs**: `/var/log/supervisor/`
- **IBC logs**: View with `supervisorctl tail ibc`
- **SSH logs**: View with `supervisorctl tail ssh-tunnel`

### Common Log Patterns

| Pattern | Meaning |
|---------|---------|
| `Connection refused` | Service not running or port not accessible |
| `Permission denied` | SSH key or file permission issues |
| `Login failed` | Incorrect IB credentials |
| `FATAL` in supervisord | Service configuration error |
| `java.net.ConnectException` | Network connectivity issue |

### Reset to Clean State

```bash
# Stop and remove container
docker-compose down

# Remove container and images
docker-compose down --rmi all

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up -d
```
