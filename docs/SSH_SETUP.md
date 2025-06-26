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

- Remote server with SSH access and Docker installed
- Client machine where you'll run trading applications
- SSH key pair for authentication
- Basic understanding of SSH concepts

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

## Step 2: Configure Client Machine SSH

### Install SSH Client (if needed)

```bash
# Ubuntu/Debian
sudo apt-get install openssh-client

# macOS (usually pre-installed)
# Windows: Install OpenSSH client or use WSL
```

### Copy Public Key to Server

```bash
# Method 1: Using ssh-copy-id (recommended)
ssh-copy-id -i ~/.ssh/ib_tunnel.pub user@your-server.com

# Method 2: Manual copy
scp ~/.ssh/ib_tunnel.pub user@your-server.com:~/
ssh user@your-server.com "mkdir -p ~/.ssh && cat ~/ib_tunnel.pub >> ~/.ssh/authorized_keys && rm ~/ib_tunnel.pub"

# Method 3: Using SSH config alias
ssh-copy-id -i ~/.ssh/ib_tunnel.pub ib-server
```

### Test SSH Connection

```bash
# Test connection without tunnel
ssh -i ~/.ssh/ib_tunnel user@your-server.com "echo 'SSH connection successful'"

# Or using SSH config
ssh ib-server "echo 'SSH connection successful'"
```

## Step 3: Configure Container

### Environment Variables

Update your `.env` file on the server:

```bash
# Basic SSH tunnel configuration
SSH_TUNNEL=yes
SSH_USER_TUNNEL=user@client-machine.com
SSH_REMOTE_PORT=4001

# Optional: Additional tunneled services
SSH_VNC_PORT=5900
SSH_RDP_PORT=3389

# Authentication
SSH_PASSPHRASE=your_key_passphrase
# Or use passphrase file
SSH_PASSPHRASE_FILE=/path/to/passphrase.txt

# Advanced SSH options
SSH_OPTIONS=-o ServerAliveInterval=30
SSH_ALIVE_INTERVAL=20
SSH_ALIVE_COUNT=3
SSH_RESTART=5
```

### Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'
services:
  ib-gateway:
    image: ib-gateway:latest
    network_mode: host
    environment:
      # SSH Tunnel Settings
      SSH_TUNNEL: "yes"
      SSH_USER_TUNNEL: "${SSH_USER_TUNNEL}"
      SSH_REMOTE_PORT: "${SSH_REMOTE_PORT:-4001}"
      SSH_VNC_PORT: "${SSH_VNC_PORT:-}"
      SSH_PASSPHRASE: "${SSH_PASSPHRASE:-}"

      # Disable local socat (not needed with SSH-only)
      ENABLE_SOCAT: "no"

      # IB Configuration
      TRADING_MODE: "${TRADING_MODE}"
      IB_USER: "${IB_USER}"
      IB_PASSWORD: "${IB_PASSWORD}"
    volumes:
      # Mount SSH keys
      - ~/.ssh:/home/ibuser/.ssh:ro
      # Optional: Custom SSH config
      - ./ssh_config:/home/ibuser/.ssh/config:ro
    restart: always
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

## Step 5: Start and Test

### Start the Container

```bash
# On the server
docker-compose up -d

# Check tunnel status
docker-compose exec ib-gateway supervisorctl status ssh-tunnel

# View SSH logs
docker-compose exec ib-gateway supervisorctl tail -f ssh-tunnel
```

### Test from Client

```bash
# Test API connection
telnet localhost 4001

# Test with curl
curl -v telnet://localhost:4001

# Test VNC (if enabled)
vncviewer localhost:5900
```

## Troubleshooting SSH Tunnels

### Common Issues

#### 1. SSH Connection Refused

```bash
# Check SSH service on client
sudo systemctl status ssh

# Check firewall
sudo ufw status

# Test direct SSH connection
ssh user@client-machine.com
```

#### 2. Permission Denied

```bash
# Check key permissions
ls -la ~/.ssh/ib_tunnel*

# Fix permissions
chmod 600 ~/.ssh/ib_tunnel
chmod 644 ~/.ssh/ib_tunnel.pub

# Check authorized_keys on client
cat ~/.ssh/authorized_keys | grep ib-tunnel
```

#### 3. Tunnel Not Establishing

```bash
# Check container SSH process
docker-compose exec ib-gateway pgrep ssh

# Check SSH logs
docker-compose exec ib-gateway supervisorctl tail ssh-tunnel

# Manual tunnel test
docker-compose exec ib-gateway ssh -i /home/ibuser/.ssh/ib_tunnel \
  -R 4001:localhost:4001 user@client-machine.com
```

### Debug Commands

```bash
# Enable SSH debug output
SSH_OPTIONS="-v"  # Add to environment

# Check tunnel connectivity
docker-compose exec ib-gateway netstat -tlnp | grep ssh

# Test SSH key authentication
docker-compose exec ib-gateway ssh-keygen -y -f /home/ibuser/.ssh/ib_tunnel

# Check SSH agent
docker-compose exec ib-gateway ssh-add -l
```

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

### Monitoring

```bash
# Log all SSH activity
sudo tail -f /var/log/auth.log | grep ssh

# Monitor tunnel connections
netstat -tlnp | grep :4001

# Set up alerts for failed connections
# (Implementation depends on your monitoring system)
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

### High Availability

```bash
# Use multiple SSH targets for redundancy
SSH_USER_TUNNEL="primary@client1.com,backup@client2.com"

# Automatic failover script
#!/bin/bash
for target in primary@client1.com backup@client2.com; do
    if ssh -q -o ConnectTimeout=5 $target exit; then
        export SSH_USER_TUNNEL=$target
        break
    fi
done
```

### SSH Bastion Host

```yaml
# Route through bastion host
environment:
  SSH_OPTIONS: "-o ProxyCommand='ssh bastion nc %h %p'"
  SSH_USER_TUNNEL: "user@internal-client"
```

## Automation Scripts

### Setup Script

```bash
#!/bin/bash
# setup_ssh_tunnel.sh

set -e

CLIENT_HOST="$1"
CLIENT_USER="$2"

if [ $# -ne 2 ]; then
    echo "Usage: $0 <client_host> <client_user>"
    exit 1
fi

# Generate SSH key
ssh-keygen -t ed25519 -f ~/.ssh/ib_tunnel -N ""

# Copy key to client
ssh-copy-id -i ~/.ssh/ib_tunnel.pub "${CLIENT_USER}@${CLIENT_HOST}"

# Update .env file
cat >> .env << EOF
SSH_TUNNEL=yes
SSH_USER_TUNNEL=${CLIENT_USER}@${CLIENT_HOST}
SSH_REMOTE_PORT=4001
EOF

echo "SSH tunnel configured for ${CLIENT_USER}@${CLIENT_HOST}"
```

### Health Check Script

```bash
#!/bin/bash
# check_tunnel.sh

# Check if tunnel process is running
if ! docker-compose exec -T ib-gateway pgrep ssh >/dev/null; then
    echo "❌ SSH tunnel process not running"
    exit 1
fi

# Check if tunnel is accessible
if ! timeout 5 bash -c "</dev/tcp/localhost/4001" 2>/dev/null; then
    echo "❌ API port not accessible through tunnel"
    exit 1
fi

echo "✅ SSH tunnel is healthy"
```

## Performance Tuning

### Optimize SSH Settings

```bash
# In ssh_config or SSH_OPTIONS
Compression yes
TCPKeepAlive yes
ServerAliveInterval 30
ServerAliveCountMax 3
```

### Monitor Performance

```bash
# Check tunnel latency
ping -c 5 client-machine.com

# Monitor bandwidth usage
iftop -i <interface>

# Check CPU usage of SSH process
docker-compose exec ib-gateway top -p $(pgrep ssh)
```

Update `docker-compose.yml` to mount SSH keys:

```yaml
volumes:
  - ~/.ssh:/home/ibuser/.ssh:ro
```

## Step 4: Start Container

```bash
docker-compose up -d
```

## Step 5: Test Connection

From your local machine:

```bash
# Test IB Gateway API connection
telnet your-server.com 4001

# Test VNC connection (if enabled)
vncviewer your-server.com:5900
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

## Security Best Practices

1. **Use Strong SSH Keys**: Prefer Ed25519 over RSA
2. **Protect Private Keys**: Use passphrases and proper file permissions
3. **Limit SSH Access**: Use `authorized_keys` restrictions if needed
4. **Regular Key Rotation**: Update SSH keys periodically
5. **Monitor Connections**: Check SSH logs for unauthorized access

## Troubleshooting

### SSH Connection Issues

```bash
# Check container logs
docker-compose logs ib-gateway

# Test SSH connection manually
ssh -i ~/.ssh/ib_tunnel user@your-server.com

# Check SSH agent
docker-compose exec ib-gateway ssh-add -l
```

### Port Already in Use

```bash
# Check what's using the port
sudo netstat -tlnp | grep :4001

# Kill existing process if needed
sudo kill $(sudo lsof -t -i:4001)
```

### Tunnel Keeps Disconnecting

- Increase `SSH_ALIVE_INTERVAL` and `SSH_ALIVE_COUNT`
- Check network stability
- Verify SSH server configuration allows keep-alive

## Example Configurations

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
