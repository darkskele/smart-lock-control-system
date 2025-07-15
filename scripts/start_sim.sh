#!/bin/bash
set -e

NUM_DEVICES=4  # Change this to scale
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BROKER="$PROJECT_ROOT/broker"
PASSWD_FILE="$BROKER/passwd"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
CERTS_DIR="$PROJECT_ROOT/certs"

if [[ "$1" == "--no-up" ]]; then
  GENERATE_ONLY=true
else
  GENERATE_ONLY=false
fi

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

echo "Returning to project root..."
cd "$PROJECT_ROOT"

if [ "$GENERATE_ONLY" = false ]; then
  echo "Restarting services with Docker Compose..."
  docker-compose down
  docker-compose up -d --build

  echo "Opening Windows Terminal tabs from PowerShell..."
  powershell.exe -Command '
    wt.exe new-tab --title "MQTT Broker" wsl -e bash -c "docker logs -f mqtt-broker" ; `
    wt.exe new-tab --title "lock-01" wsl -e bash -c "docker logs -f lock-01" ; `
    wt.exe new-tab --title "lock-02" wsl -e bash -c "docker logs -f lock-02" ; `
    wt.exe new-tab --title "lock-03" wsl -e bash -c "docker logs -f lock-03" ; `
    wt.exe new-tab --title "lock-04" wsl -e bash -c "docker logs -f lock-04" ; `
    wt.exe new-tab --title "Smart Lock CLI" wsl -e bash -c "docker attach cli"
  '
  echo "Broker logs:"
  docker logs mqtt-broker --tail 10

  for i in $(seq -w 1 $NUM_DEVICES); do
    DEVICE_ID="lock-0$i"
    echo "Device '$DEVICE_ID' logs:"
    docker logs "$DEVICE_ID" --tail 10
  done
fi