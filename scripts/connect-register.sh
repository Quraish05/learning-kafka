#!/usr/bin/env bash
set -euo pipefail

# Registers both source & sink (sink is optional).
# Run from repo root (where docker compose lives).

echo "Registering file-source-orders..."
curl -s -X PUT -H "Content-Type: application/json" \
  --data @connect/connector-file-source.json \
  http://localhost:8083/connectors/file-source-orders/config | jq .

echo
echo "Registering file-sink-orders (optional)..."
curl -s -X PUT -H "Content-Type: application/json" \
  --data @connect/connector-file-sink.json \
  http://localhost:8083/connectors/file-sink-orders/config | jq .
