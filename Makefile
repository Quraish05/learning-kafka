cluster-up:
	docker compose -f docker-compose.cluster.yml up -d

topics:
	./scripts/create-food-topics.sh

health:
	./scripts/cluster-health.sh

failover:
	./scripts/demo-failover.sh

produce:
	python3 -m src.producer_partitioned --count 30 --delay 0.1 --acks all

consume-one:
	python3 -m src.consumer_group_demo --group group-a --from-beginning
