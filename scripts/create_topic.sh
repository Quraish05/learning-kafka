#!/usr/bin/env bash
set -euo pipefail

BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP:-localhost:9092}"
TOPIC="${TOPIC:-demo.orders}"
PARTITIONS="${PARTITIONS:-3}"
REPLICATION="${REPLICATION:-1}"

echo "Creating topic: $TOPIC (partitions=$PARTITIONS, rf=$REPLICATION) on $BOOTSTRAP_SERVER"
# Use Docker exec to run kafka-topics inside the Kafka container
# Note: Confluent Kafka uses kafka-topics (without .sh extension)
docker exec kafka kafka-topics \
  --create \
  --if-not-exists \
  --topic "$TOPIC" \
  --partitions "$PARTITIONS" \
  --replication-factor "$REPLICATION" \
  --bootstrap-server "$BOOTSTRAP_SERVER"

echo "Topic list:"
docker exec kafka kafka-topics --list --bootstrap-server "$BOOTSTRAP_SERVER"