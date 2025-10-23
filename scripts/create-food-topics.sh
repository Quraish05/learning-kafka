#!/usr/bin/env bash
set -euo pipefail

# Use the INTERNAL listener inside the compose network
BOOTSTRAP="kafka-1:19092"
KAFKA_BIN="/opt/kafka/bin"

topics=(
  "demo.orders:3:3"
  "demo.payments:3:3"
  "demo.restaurant:3:3"
  "demo.delivery:3:3"
)

for t in "${topics[@]}"; do
  IFS=':' read -r name parts rf <<< "$t"
  docker compose -f docker-compose.cluster.yml exec -T kafka-cli \
    ${KAFKA_BIN}/kafka-topics.sh \
    --bootstrap-server "$BOOTSTRAP" \
    --create --if-not-exists \
    --topic "$name" \
    --partitions "$parts" \
    --replication-factor "$rf"
done

echo "All topics created."
