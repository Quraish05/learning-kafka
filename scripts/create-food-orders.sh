#!/usr/bin/env bash
set -euo pipefail

BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP:-localhost:9092}"
TOPIC="${TOPIC:-demo.orders}"
PARTITIONS="${PARTITIONS:-3}"
REPLICATION="${REPLICATION:-1}"
KAFKA_BIN="/opt/kafka/bin"

echo "Creating topic: $TOPIC (partitions=$PARTITIONS, rf=$REPLICATION) on $BOOTSTRAP_SERVER"
# Use Docker exec to run kafka-topics inside the Kafka container
# Note: Confluent Kafka uses kafka-topics (without .sh extension)
docker exec kafka-1 ${KAFKA_BIN}/kafka-topics.sh \
  --create \
  --topic food.orders \
  --partitions 6 \
  --replication-factor 3 \
  --bootstrap-server kafka-1:9092,kafka-2:9092,kafka-3:9092
