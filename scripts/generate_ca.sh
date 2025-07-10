#!/bin/bash
set -e

# Certificate directory hardcoded to root
CERTS_DIR="./certs"
mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

if [[ -f ca.crt && -f ca.key ]]; then
  echo "CA already exists. Skipping generation."
  exit 0
fi

# Just CA generation
echo "Generating CA private key and certificate..."
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 365 -key ca.key -out ca.crt -subj "/CN=MQTT CA"

echo "CA generated:"
ls -l ca.*
