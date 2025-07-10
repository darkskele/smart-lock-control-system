.PHONY: start stop logs rebuild

# Start the MQTT broker:
# - Runs the startup script, which handles TLS generation, permission fixes,
#   container restart, and logs display.
start:
	./scripts/start_sim.sh

# Stop the MQTT broker container and remove the network.
stop:
	docker-compose down

# Show logs from the running MQTT broker container.
logs_broker:
	docker logs mqtt-broker
# Show logs from the running device container.
logs_lock_01:
	docker logs lock-01 --tail 20
logs_lock_02:
	docker logs lock-02 --tail 20
logs_lock_03:
	docker logs lock-03 --tail 20
logs_lock_04:
	docker logs lock-04 --tail 20

# Fully rebuild the container image without using cache.
rebuild:
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
