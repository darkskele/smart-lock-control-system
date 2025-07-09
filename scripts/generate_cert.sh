#!/bin/bash
set -e

# Usage: ./generate_cert.sh <name> <target_dir>
NAME="$1"
TARGET_DIR="$2"

if [[ -z "$NAME" || -z "$TARGET_DIR" ]]; then
  echo "Usage: $0 <name> <target_dir>"
  exit 1
fi

# Root of the project
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CA_DIR="$PROJECT_ROOT/certs"
CA_CERT="$CA_DIR/ca.crt"
CA_KEY="$CA_DIR/ca.key"

# Make dir
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

if [[ -f server.crt && -f server.key ]]; then
  echo "Certs for '$NAME' already exist in $TARGET_DIR. Skipping."
  exit 0
fi

# Server key
echo "Generating private key for '$NAME'..."
openssl genrsa -out server.key 2048

# CSR 
echo "Creating CSR config for '$NAME'..."
# Make sure DNS.1 points to broker name in docker compose
cat > server.cnf <<EOF
[ req ]
default_bits = 2048
prompt = no
default_md = sha256
req_extensions = req_ext
distinguished_name = dn

[ dn ]
CN = $NAME

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = mqtt-broker
DNS.2 = localhost
EOF

echo "Generating CSR..."
openssl req -new -key server.key -out server.csr -config server.cnf

# Signing
echo "Signing with CA from $CA_CERT..."
openssl x509 -req -in server.csr \
  -CA "$CA_CERT" \
  -CAkey "$CA_KEY" \
  -CAcreateserial \
  -out server.crt \
  -days 365 \
  -extensions req_ext \
  -extfile server.cnf

rm -f server.csr

echo "Generated cert for '$NAME' in: $TARGET_DIR"
openssl x509 -in server.crt -noout -subject -issuer -dates -ext subjectAltName
