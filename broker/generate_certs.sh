set -e

# Directory to store generated certificates
CERTS_DIR="./broker/certs"

# Create the certs directory if it doesn't exist
mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

# Only generate if certs are missing
if [[ -f server.crt && -f server.key && -f ca.crt && -f ca.key ]]; then
  echo "TLS certificates already exist. Skipping generation."
  exit 0
fi

# Generate a private key for the Certificate Authority
echo "Generating CA private key and certificate..."
openssl genrsa -out ca.key 2048

# Create a self-signed CA certificate
openssl req -new -x509 -days 365 -key ca.key -out ca.crt -subj "/CN=MQTT CA"

# Generate a private key for the MQTT server
echo "Generating server key and CSR..."
openssl genrsa -out server.key 2048

# Create a certificate signing request (CSR) for the server certificate
openssl req -new -key server.key -out server.csr -subj "/CN=localhost"

# Use the CA to sign the server certificate
echo "Signing server cert with CA..."
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 365

# List the generated files as confirmation
echo "TLS certificates generated in $CERTS_DIR:"
ls -l
