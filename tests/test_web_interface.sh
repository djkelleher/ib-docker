# Check if HTTP server is enabled
docker-compose exec ib-gateway env | grep SUPERVISORD_UI_PORT

# Check if service is running
docker-compose exec ib-gateway netstat -tlnp | grep 9001
