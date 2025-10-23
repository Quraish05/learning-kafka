#!/usr/bin/env bash
set -euo pipefail

BOOTSTRAP="kafka-1:19092"
KAFKA_BIN="/opt/kafka/bin"

echo "Stopping broker kafka-2 to simulate failure..."
docker compose -f docker-compose.cluster.yml stop kafka-2
sleep 5

echo
echo "Describe topic to see new leaders/ISR after failover:"
docker compose -f docker-compose.cluster.yml exec -T kafka-cli \
  ${KAFKA_BIN}/kafka-topics.sh \
  --bootstrap-server "$BOOTSTRAP" --describe --topic demo.orders

echo
echo "Restarting broker kafka-2..."
docker compose -f docker-compose.cluster.yml start kafka-2
sleep 8

echo
echo "Describe topic again (ISR should recover):"
docker compose -f docker-compose.cluster.yml exec -T kafka-cli \
  ${KAFKA_BIN}/kafka-topics.sh \
  --bootstrap-server "$BOOTSTRAP" --describe --topic demo.orders
