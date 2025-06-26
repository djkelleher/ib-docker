# Check SSH process
docker-compose exec ib-gateway pgrep ssh

# Test SSH connection manually
docker-compose exec ib-gateway ssh -T user@server.com
