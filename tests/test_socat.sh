# Check socat processes
docker-compose exec ib-gateway pgrep socat

# Check socat configuration
docker-compose exec ib-gateway ps aux | grep socat
