# Check if HTTP server is enabled
docker-compose exec ib-gateway env | grep HTTP_SERVER_PORT

# Check if service is running
docker-compose exec ib-gateway netstat -tlnp | grep 9001
