.PHONY: start stop logs rebuild

# Start the MQTT broker:
# - Runs the startup script, which handles TLS generation, permission fixes,
#   container restart, and logs display.
start:
	./scripts/start_broker.sh

# Stop the MQTT broker container and remove the network.
stop:
	docker-compose down

# Show logs from the running MQTT broker container.
logs:
	docker logs mqtt-broker

# Fully rebuild the container image without using cache.
rebuild:
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
