#!/bin/bash
set -e

CERTS_DIR="./broker/certs"
PASSWD_FILE="./broker/passwd"

# Fix permissions on passwd file
if [ -f "$PASSWD_FILE" ]; then
  if chmod 600 "$PASSWD_FILE" 2>/dev/null; then
    echo "Password file permissions set to 600."
  else
    echo "Warning: could not change permissions on $PASSWD_FILE. Try: sudo chown $USER $PASSWD_FILE"
    exit 0
  fi
fi

# Generate certs if missing
./broker/generate_certs.sh

# Launch Docker Compose
echo "Starting MQTT broker..."
docker-compose down
docker-compose up -d

# Show logs
echo "Broker logs:"
docker logs mqtt-broker
