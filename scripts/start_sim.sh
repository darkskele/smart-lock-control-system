#!/bin/bash
set -e

NUM_DEVICES=4  # Change this to scale
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BROKER="$PROJECT_ROOT/broker"
PASSWD_FILE="$BROKER/passwd"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
CERTS_DIR="$PROJECT_ROOT/certs"

echo "Fixing password file permissions..."
if [ -f "$PASSWD_FILE" ]; then
  if [ ! -O "$PASSWD_FILE" ]; then
    echo "Skipping chmod: $PASSWD_FILE not owned by current user ($USER)"
  else
    if chmod 600 "$PASSWD_FILE" 2>/dev/null; then
      echo "Password file permissions set to 600."
    else
      echo "chmod failed, trying with sudo..."
      if sudo chmod 600 "$PASSWD_FILE"; then
        echo "Password file permissions set to 600 with sudo."
      else
        echo "Failed to fix permissions. Try: sudo chown $USER $PASSWD_FILE"
        exit 1
      fi
    fi
  fi
fi

echo "Generating CA if needed..."
cd "$PROJECT_ROOT"
bash "$SCRIPTS_DIR/generate_ca.sh"

echo "Generating TLS certificate for broker..."
bash "$SCRIPTS_DIR/generate_cert.sh" broker ./broker/certs

for i in $(seq -w 1 $NUM_DEVICES); do
  DEVICE_ID="lock-0$i"
  DEVICE_CERT_DIR="$PROJECT_ROOT/src/simulator/simulators_devices/$DEVICE_ID/certs"

  echo "Generating TLS certificate for device '$DEVICE_ID'..."
  bash "$SCRIPTS_DIR/generate_cert.sh" "$DEVICE_ID" "$DEVICE_CERT_DIR"

  echo "Creating password entry for '$DEVICE_ID'..."
  docker run --rm -v "$BROKER:/mosquitto/config" eclipse-mosquitto \
    mosquitto_passwd -b /mosquitto/config/passwd "$DEVICE_ID" "pwd$i"
done

echo "Returning to project root..."
cd "$PROJECT_ROOT"

echo "Restarting services with Docker Compose..."
docker-compose down
docker-compose up -d --build

echo "Broker logs:"
docker logs mqtt-broker --tail 10

for i in $(seq -w 1 $NUM_DEVICES); do
  DEVICE_ID="lock-0$i"
  echo "Device '$DEVICE_ID' logs:"
  docker logs "$DEVICE_ID" --tail 10
done
