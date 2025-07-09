#!/bin/bash
set -e

DEVICE_ID="lock-01"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BROKER="$PROJECT_ROOT/broker"
PASSWD_FILE="$BROKER/passwd"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
CERTS_DIR="$PROJECT_ROOT/certs"

echo "Fixing password file permissions..."
if [ -f "$PASSWD_FILE" ]; then
  if chmod 600 "$PASSWD_FILE" 2>/dev/null; then
    echo "Password file permissions set to 600."
  else
    echo "Warning: could not change permissions on $PASSWD_FILE"
    echo "   Try: sudo chown $USER $PASSWD_FILE"
    exit 1
  fi
fi

echo "Generating CA if needed..."
cd "$PROJECT_ROOT"
bash $SCRIPTS_DIR/generate_ca.sh

echo "Generating TLS certificate for broker..."
cd "$PROJECT_ROOT"
bash $SCRIPTS_DIR/generate_cert.sh broker ./broker/certs

echo "Generating TLS certificate for device '$DEVICE_ID'..."
bash $SCRIPTS_DIR/generate_cert.sh lock-01 ./simulator/simulators_devices/lock-01/certs

echo "Returning to project root..."
cd "$PROJECT_ROOT"

echo "Starting services with Docker Compose..."
docker-compose down
docker-compose up -d --build

echo "Broker logs:"
docker logs mqtt-broker --tail 10

echo "Device '$DEVICE_ID' logs:"
docker logs "$DEVICE_ID" --tail 10
