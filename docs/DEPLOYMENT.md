# Deployment Guide

This guide covers different deployment scenarios for the IB Docker container in various environments.

## Deployment Scenarios

### 1. Local Development

**Use Case**: Development and testing on local machine

```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  ib-gateway:
    image: ib-gateway:latest
    network_mode: host
    restart: unless-stopped
    environment:
      TRADING_MODE: paper
      ENABLE_SOCAT: "no"
      VNC_PWD: "devpass123"
      HTTP_SERVER_PORT: 9001
    volumes:
      - ./dev-config:/opt/ibc/config
      - ./logs:/var/log/supervisor
```

**Features:**
- Paper trading mode
- VNC access for debugging
- Supervisord web interface
- Local log persistence

**Start Command:**
```bash
docker-compose -f docker-compose.dev.yml up -d
```

### 2. Remote Server with SSH Tunnel

**Use Case**: Secure remote access for production trading

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  ib-gateway:
    image: ib-gateway:latest
    network_mode: host
    restart: always
    environment:
      TRADING_MODE: live
      SSH_TUNNEL: "yes"
      SSH_USER_TUNNEL: "trader@client.example.com"
      SSH_REMOTE_PORT: 4001
      SSH_VNC_PORT: 5900
      ENABLE_SOCAT: "no"
      AUTO_RESTART_TIME: "23:55 PM"
      RELOGIN_AFTER_TWOFA_TIMEOUT: "yes"
    volumes:
      - ~/.ssh:/home/ibuser/.ssh:ro
      - ./prod-settings:/home/ibuser/tws_settings
      - /etc/localtime:/etc/localtime:ro
```

**Features:**
- Live trading mode
- SSH tunnel security
- Daily auto-restart
- Persistent settings
- 2FA timeout handling

### 3. Cloud VPS Deployment

**Use Case**: Cloud-hosted container with external access

```yaml
# docker-compose.cloud.yml
version: '3.8'
services:
  ib-gateway:
    image: ib-gateway:latest
    ports:
      - "127.0.0.1:4001:4003"  # Localhost only
      - "127.0.0.1:4002:4004"
    restart: always
    environment:
      TRADING_MODE: ${TRADING_MODE}
      ENABLE_SOCAT: "yes"
      HTTP_SERVER_PORT: 9001
      HTTP_SERVER_USER: "admin"
      HTTP_SERVER_PASS: "${SUPERVISOR_PASSWORD}"
    volumes:
      - ib_data:/home/ibuser/tws_settings
      - /var/log/ib-docker:/var/log/supervisor

volumes:
  ib_data:
```

**Security Features:**
- Bind to localhost only
- Password-protected web interface
- Persistent data volume
- Centralized logging

### 4. High Availability Setup

**Use Case**: Production environment with redundancy

```yaml
# docker-compose.ha.yml
version: '3.8'
services:
  ib-gateway-primary:
    image: ib-gateway:latest
    network_mode: host
    restart: always
    environment:
      TRADING_MODE: live
      AUTO_RESTART_TIME: "23:55 PM"
      COLD_RESTART_TIME: "02:00 AM"
      SAVE_TWS_SETTINGS: "Every 10 mins"
      HTTP_SERVER_PORT: 9001
    volumes:
      - primary_data:/home/ibuser/tws_settings
      - ~/.ssh:/home/ibuser/.ssh:ro
    healthcheck:
      test: ["CMD", "supervisorctl", "status"]
      interval: 30s
      timeout: 10s
      retries: 3

  ib-gateway-backup:
    image: ib-gateway:latest
    network_mode: host
    restart: "no"  # Manual failover
    environment:
      TRADING_MODE: live
      HTTP_SERVER_PORT: 9002
    volumes:
      - backup_data:/home/ibuser/tws_settings
      - ~/.ssh:/home/ibuser/.ssh:ro
    profiles:
      - backup

volumes:
  primary_data:
  backup_data:
```

**Features:**
- Primary/backup configuration
- Health checks
- Separate data volumes
- Manual failover control

## Environment-Specific Configurations

### Development Environment

```bash
# .env.dev
TRADING_MODE=paper
ENABLE_SOCAT=no
VNC_PWD=devpass
HTTP_SERVER_PORT=9001
AUTO_RESTART_TIME=
IB_USER=your_paper_username
IB_PASSWORD=your_paper_password
```

### Production Environment

```bash
# .env.prod
TRADING_MODE=live
SSH_TUNNEL=yes
SSH_USER_TUNNEL=trader@client.example.com
ENABLE_SOCAT=no
AUTO_RESTART_TIME=23:55 PM
RELOGIN_AFTER_TWOFA_TIMEOUT=yes
SAVE_TWS_SETTINGS=Every 15 mins
IB_USER=your_live_username
IB_PASSWORD=your_live_password
```

## Container Orchestration

### Docker Swarm

```yaml
# docker-stack.yml
version: '3.8'
services:
  ib-gateway:
    image: ib-gateway:latest
    networks:
      - ib-network
    environment:
      TRADING_MODE: live
      ENABLE_SOCAT: "yes"
    volumes:
      - ib_data:/home/ibuser/tws_settings
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: any
        delay: 30s
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

networks:
  ib-network:
    driver: overlay

volumes:
  ib_data:
    driver: local
```

Deploy with:
```bash
docker stack deploy -c docker-stack.yml ib-trading
```

### Kubernetes

```yaml
# kubernetes.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ib-gateway
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ib-gateway
  template:
    metadata:
      labels:
        app: ib-gateway
    spec:
      containers:
      - name: ib-gateway
        image: ib-gateway:latest
        env:
        - name: TRADING_MODE
          value: "live"
        - name: ENABLE_SOCAT
          value: "yes"
        - name: IB_USER
          valueFrom:
            secretKeyRef:
              name: ib-credentials
              key: username
        - name: IB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: ib-credentials
              key: password
        volumeMounts:
        - name: tws-settings
          mountPath: /home/ibuser/tws_settings
        - name: ssh-keys
          mountPath: /home/ibuser/.ssh
          readOnly: true
        resources:
          limits:
            memory: "4Gi"
            cpu: "2"
          requests:
            memory: "2Gi"
            cpu: "1"
      volumes:
      - name: tws-settings
        persistentVolumeClaim:
          claimName: ib-gateway-pvc
      - name: ssh-keys
        secret:
          secretName: ssh-keys
          defaultMode: 0600

---
apiVersion: v1
kind: Service
metadata:
  name: ib-gateway-service
spec:
  selector:
    app: ib-gateway
  ports:
  - name: api-live
    port: 4001
    targetPort: 4003
  - name: api-paper
    port: 4002
    targetPort: 4004
  type: ClusterIP
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy IB Gateway

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Deploy to server
      uses: appleboy/ssh-action@v0.1.4
      with:
        host: ${{ secrets.HOST }}
        username: ${{ secrets.USERNAME }}
        key: ${{ secrets.SSH_KEY }}
        script: |
          cd /opt/ib-docker
          git pull origin main
          docker-compose pull
          docker-compose up -d --remove-orphans

    - name: Health check
      run: |
        sleep 30
        curl -f http://${{ secrets.HOST }}:9001 || exit 1
```

### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - build
  - deploy

build:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

deploy:
  stage: deploy
  script:
    - ssh $DEPLOY_USER@$DEPLOY_HOST "
        cd /opt/ib-docker &&
        docker-compose pull &&
        docker-compose up -d
      "
  only:
    - main
```

## Monitoring and Logging

### Monitoring Setup

```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  ib-gateway:
    # ... main service config ...

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin123
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  grafana_data:
```

### Centralized Logging

```yaml
# logging configuration
services:
  ib-gateway:
    logging:
      driver: syslog
      options:
        syslog-address: "tcp://localhost:514"
        tag: "ib-gateway"
```

## Backup and Recovery

### Automated Backup Script

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/opt/backups/ib-docker"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup container data
docker run --rm \
  -v ib_data:/data \
  -v "$BACKUP_DIR:/backup" \
  alpine tar czf "/backup/ib-data-$DATE.tar.gz" /data

# Backup configuration
tar czf "$BACKUP_DIR/config-$DATE.tar.gz" \
  docker-compose.yml .env config/

# Cleanup old backups (keep 7 days)
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

### Recovery Process

```bash
#!/bin/bash
# restore.sh

BACKUP_FILE="$1"
if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

# Stop container
docker-compose down

# Restore data
docker run --rm \
  -v ib_data:/data \
  -v "$(dirname $BACKUP_FILE):/backup" \
  alpine tar xzf "/backup/$(basename $BACKUP_FILE)" -C /

# Start container
docker-compose up -d

echo "Restore completed from: $BACKUP_FILE"
```

## Security Hardening

### Production Security Checklist

- [ ] Use SSH tunnels instead of direct port exposure
- [ ] Implement strong passwords for all services
- [ ] Regular security updates for base images
- [ ] Network segmentation
- [ ] Log monitoring and alerting
- [ ] Regular backups
- [ ] SSH key rotation
- [ ] Firewall configuration

### Security Configuration

```bash
# Firewall setup (UFW example)
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow from trusted.client.ip to any port 22
ufw enable

# Docker security options
docker run --security-opt no-new-privileges \
  --read-only \
  --tmpfs /tmp \
  ib-gateway:latest
```

## Performance Tuning

### Resource Limits

```yaml
services:
  ib-gateway:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
        reservations:
          memory: 2G
          cpus: '1'
```

### JVM Tuning

```bash
# Custom Java options
JAVA_OPTS="-Xmx2g -Xms1g -XX:+UseG1GC"
```

## Maintenance

### Regular Maintenance Tasks

```bash
#!/bin/bash
# maintenance.sh

# Update images
docker-compose pull

# Clean unused resources
docker system prune -f

# Restart services
docker-compose restart

# Check health
./tests/test_ssh_tunnel.sh
```

### Automated Updates

```bash
# Cron job for weekly updates
0 2 * * 0 cd /opt/ib-docker && ./maintenance.sh >> /var/log/ib-maintenance.log 2>&1
```
