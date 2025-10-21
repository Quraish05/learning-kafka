#!/usr/bin/env bash
set -euo pipefail
BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP:-localhost:9092}"
TOPIC="${TOPIC:-demo.orders}"

# Use Docker exec to run kafka-topics inside the Kafka container
# Note: Confluent Kafka uses kafka-topics (without .sh extension)
docker exec kafka kafka-topics --describe --topic "$TOPIC" --bootstrap-server "$BOOTSTRAP_SERVER"
