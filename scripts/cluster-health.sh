#!/usr/bin/env bash
set -euo pipefail

BOOTSTRAP="kafka-1:19092"
KAFKA_BIN="/opt/kafka/bin"

echo "===== Metadata quorum status ====="
docker compose -f docker-compose.cluster.yml exec -T kafka-cli \
  ${KAFKA_BIN}/kafka-metadata-quorum.sh \
  --bootstrap-server "$BOOTSTRAP" describe --status

echo
echo "===== demo.orders description ====="
docker compose -f docker-compose.cluster.yml exec -T kafka-cli \
  ${KAFKA_BIN}/kafka-topics.sh \
  --bootstrap-server "$BOOTSTRAP" --describe --topic demo.orders
