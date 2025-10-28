#!/usr/bin/env bash
set -euo pipefail

# Check if kafka-1 exists (cluster mode) or kafka (single mode)
if docker ps --format '{{.Names}}' | grep -q '^kafka-1$'; then
  # Cluster mode: use INTERNAL listeners
  BOOTSTRAP_SERVER="kafka-1:19092,kafka-2:19092,kafka-3:19092"
  CONTAINER="kafka-1"
elif docker ps --format '{{.Names}}' | grep -q '^kafka$'; then
  # Single mode
  BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP:-localhost:9092}"
  CONTAINER="kafka"
else
  echo "Error: No Kafka container found (kafka or kafka-1)"
  exit 1
fi

GROUP="${1:-group-a}"

echo "Describing consumer group '$GROUP' in $CONTAINER..."
docker exec "$CONTAINER" /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server "$BOOTSTRAP_SERVER" \
  --group "$GROUP" \
  --describe



