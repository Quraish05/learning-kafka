#!/usr/bin/env bash
set -euo pipefail
BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP:-localhost:9092}"

# Use Docker exec to run kafka-consumer-groups inside the Kafka container
# Note: Confluent Kafka uses kafka-consumer-groups (without .sh extension)
docker exec kafka kafka-consumer-groups --bootstrap-server "$BOOTSTRAP_SERVER" --list
