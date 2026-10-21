#!/usr/bin/env bash
# Generates the RS256 key pair: auth service signs with the private key, other services verify with the public key.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .keys
if [ -f .keys/jwt_private.pem ]; then
  echo ".keys/jwt_private.pem already exists, skipping"
  exit 0
fi
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out .keys/jwt_private.pem
openssl rsa -in .keys/jwt_private.pem -pubout -out .keys/jwt_public.pem
chmod 644 .keys/jwt_public.pem .keys/jwt_private.pem
echo "keys written to .keys/"
