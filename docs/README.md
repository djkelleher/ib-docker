# Documentation Index

Welcome to the comprehensive documentation for IB Docker - a reliable, high-performance Docker solution for running Interactive Brokers Gateway and TWS.

## 📚 Documentation Overview

This documentation is organized into focused guides that cover different aspects of using and configuring the IB Docker container.

### 🚀 Getting Started

- **[Getting Started Guide](./GETTING_STARTED.md)** - Quick setup and installation
- **[Configuration Guide](./CONFIGURATION.md)** - Complete environment variable reference
- **[SSH Setup Guide](./SSH_SETUP.md)** - Secure remote access configuration

### 🔧 Advanced Topics

- **[Network Architecture](./NETWORKING.md)** - Understanding networking patterns and configurations
- **[Deployment Guide](./DEPLOYMENT.md)** - Production deployment scenarios and best practices
- **[API Integration](./API_INTEGRATION.md)** - Connect your trading applications to the API

### 🛠 Operations

- **[Troubleshooting Guide](./TROUBLESHOOTING.md)** - Diagnose and fix common issues
- **[Performance Tuning](./PERFORMANCE.md)** - Optimize for production workloads
- **[Security Guide](./SECURITY.md)** - Harden your deployment

## 📖 Quick Navigation

### For New Users
1. Start with [Getting Started Guide](./GETTING_STARTED.md)
2. Review [Configuration Guide](./CONFIGURATION.md) for your specific needs
3. Follow [SSH Setup Guide](./SSH_SETUP.md) if you need remote access

### For Developers
1. Check [API Integration Guide](./API_INTEGRATION.md) for your programming language
2. Review [Network Architecture](./NETWORKING.md) to understand connectivity
3. Use [Troubleshooting Guide](./TROUBLESHOOTING.md) when issues arise

### For DevOps/Production
1. Read [Deployment Guide](./DEPLOYMENT.md) for your environment
2. Implement [Security Guide](./SECURITY.md) recommendations
3. Set up monitoring using [Performance Tuning](./PERFORMANCE.md)

## 🎯 Common Use Cases

### Local Development
```bash
# Quick local setup for API development
git clone <repo>
cp .env.example .env
# Edit .env with your IB credentials
docker-compose up -d
```
📖 **See**: [Getting Started](./GETTING_STARTED.md) → Local Development

### Remote Production Server
```bash
# Secure production deployment with SSH tunneling
# Server setup with encrypted remote access
```
📖 **See**: [SSH Setup](./SSH_SETUP.md) + [Deployment](./DEPLOYMENT.md) → Remote Server

### Trading Application Integration
```python
# Connect your Python/Java/C#/JavaScript app
from ibapi.client import EClient
# ... connection code
```
📖 **See**: [API Integration](./API_INTEGRATION.md) → Your Language

### Multi-Environment Setup
```yaml
# Different configs for dev/staging/prod
# Environment-specific configurations
```
📖 **See**: [Configuration](./CONFIGURATION.md) + [Deployment](./DEPLOYMENT.md)

## 🔍 Find Information By Topic

### Connection Issues
- Port not accessible: [Troubleshooting](./TROUBLESHOOTING.md) → API Connection Refused
- SSH tunnel failing: [SSH Setup](./SSH_SETUP.md) → Troubleshooting
- Network configuration: [Networking](./NETWORKING.md) → Network Troubleshooting

### Security & Access
- SSH tunneling: [SSH Setup Guide](./SSH_SETUP.md)
- Network security: [Security Guide](./SECURITY.md)
- Remote access patterns: [Networking](./NETWORKING.md)

### Configuration Questions
- Environment variables: [Configuration Guide](./CONFIGURATION.md)
- Docker setup: [Getting Started](./GETTING_STARTED.md)
- Production settings: [Deployment Guide](./DEPLOYMENT.md)

### Development & Integration
- API connections: [API Integration](./API_INTEGRATION.md)
- Code examples: [API Integration](./API_INTEGRATION.md) → Language Examples
- Testing: [API Integration](./API_INTEGRATION.md) → Testing

## 🆘 Need Help?

### Troubleshooting Steps
1. **Check container status**: `docker-compose ps`
2. **Review logs**: `docker-compose logs ib-gateway`
3. **Run diagnostics**: `./tests/test_ssh_tunnel.sh`
4. **Consult**: [Troubleshooting Guide](./TROUBLESHOOTING.md)

### Common Commands
```bash
# Container management
docker-compose up -d              # Start container
docker-compose down               # Stop container
docker-compose logs -f ib-gateway # View logs
docker-compose restart ib-gateway # Restart container

# Service management (inside container)
docker-compose exec ib-gateway supervisorctl status      # Check services
docker-compose exec ib-gateway supervisorctl restart ibc # Restart IBC

# Testing
./tests/test_ssh_tunnel.sh  # Run comprehensive test
telnet localhost 4002       # Test API connection
```

### Error Code Quick Reference

| Error | Description | Solution |
|-------|-------------|----------|
| Connection refused | API port not accessible | [Troubleshooting](./TROUBLESHOOTING.md) → API Connection |
| SSH tunnel failed | SSH connection issues | [SSH Setup](./SSH_SETUP.md) → Troubleshooting |
| Container won't start | Configuration errors | [Getting Started](./GETTING_STARTED.md) → Verify Setup |
| Login failed | IB credential issues | [Configuration](./CONFIGURATION.md) → IB Credentials |

## 📋 Document Status

| Document | Status | Last Updated |
|----------|--------|--------------|
| Getting Started | ✅ Complete | Current |
| Configuration | ✅ Complete | Current |
| SSH Setup | ✅ Complete | Current |
| Networking | ✅ Complete | Current |
| Deployment | ✅ Complete | Current |
| API Integration | ✅ Complete | Current |
| Troubleshooting | ✅ Complete | Current |
| Performance | 🔄 Planned | TBD |
| Security | 🔄 Planned | TBD |

## 🤝 Contributing

Found an issue or want to improve the documentation?

1. Check existing documentation for your topic
2. Create clear, example-driven content
3. Test all commands and code examples
4. Follow the established format and style

The documentation is organized to be:
- **Focused**: Each guide covers one main topic
- **Practical**: Includes working examples and commands
- **Progressive**: From basic to advanced concepts
- **Cross-referenced**: Links between related topics

## 📄 Additional Resources

- **Main README**: [../README.md](../README.md) - Project overview
- **Docker Compose**: [../docker-compose.yml](../docker-compose.yml) - Configuration template
- **Test Scripts**: [../tests/](../tests/) - Validation and testing tools
- **Configuration Examples**: [../config/](../config/) - Sample configuration files
