cluster-up:
	docker compose -f docker-compose.cluster.yml up -d

topics:
	./scripts/create-food-topics.sh

health:
	./scripts/cluster-health.sh

failover:
	./scripts/demo-failover.sh

# Default values for produce-fast
COUNT ?= 50000
LINGER_MS ?= 20
BATCH_SIZE ?= 65536
COMPRESSION ?= lz4

produce:
	python3 -m src.producer_partitioned --count 30 --delay 0.1 --acks all

consume-one:
	python3 -m src.consumer_group_demo --group group-a --from-beginning

produce-fast:
	COUNT=$(COUNT) LINGER_MS=$(LINGER_MS) BATCH_SIZE=$(BATCH_SIZE) COMPRESSION=$(COMPRESSION) python3 src/producers/fast_order_producer.py

GROUP_ID ?= orders-cg

consume-alice:
	GROUP_ID=$(GROUP_ID) CONSUMER_NAME=alice python3 src/consumers/group_order_consumer.py

consume-bob:
	GROUP_ID=$(GROUP_ID) CONSUMER_NAME=bob python3 src/consumers/group_order_consumer.py
