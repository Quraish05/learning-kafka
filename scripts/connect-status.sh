#!/usr/bin/env bash
set -euo pipefail

echo "Connectors:"
curl -s http://localhost:8083/connectors | jq .

echo
echo "file-source-orders status:"
curl -s http://localhost:8083/connectors/file-source-orders/status | jq .

echo
echo "file-sink-orders status:"
curl -s http://localhost:8083/connectors/file-sink-orders/status | jq .
