🧩 Chapter 1 – Initial Kafka Consumer-Producer Setup with Management Scripts

Goal:
Establish a foundational Kafka producer-consumer system using Python, with command-line tools for managing topics and consumer groups. This chapter covers the migration from `confluent-kafka` to `kafka-python` and introduces essential management scripts.

📋 Overview

This chapter documents the first commit of the project, which introduced:
- A refactored producer using `kafka-python` library with environment-based configuration
- A new consumer with CLI arguments and offset tracking capabilities
- Shell scripts for managing Kafka topics and consumer groups

The implementation was guided by a ChatGPT conversation, with technical adjustments made based on practical testing and console/terminal history.

🔧 1 – Producer Refactoring (producer.py)

Migration from confluent-kafka to kafka-python

Before (old_producer.py):
```python
from confluent_kafka import Producer

producer = Producer({
    'bootstrap.servers': 'localhost:9092'
})

def delivery_report(err, msg):
    if err:
        print(f"Error: {err}")
    else:
        print(f"Message delivered {msg.value().decode('utf-8')}")
```

After (producer.py):
```python
from kafka import KafkaProducer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("TOPIC", "demo.orders")

producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP,
    acks="all",
    linger_ms=10,
    retries=3,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
)
```

Key Changes:
- Library: `confluent-kafka` → `kafka-python`
- Configuration: Hardcoded → Environment variables (`KAFKA_BOOTSTRAP`, `TOPIC`)
- Serialization: Manual encoding → Built-in serializers
- Message sending: Callback-based → Future-based with `.get()` for metadata
- Producer settings: Added `acks="all"`, `linger_ms`, and `retries` for reliability

Why kafka-python?
- Pure Python implementation (no C dependencies)
- Simpler API for basic use cases
- Better integration with Python ecosystem
- Easier debugging and maintenance

Producer Features:
- Environment-based configuration via `KAFKA_BOOTSTRAP` and `TOPIC`
- Automatic JSON serialization
- Key-value message support
- Metadata tracking (partition, offset)
- Configurable reliability settings (`acks="all"`)

Example Usage:
```bash
export KAFKA_BOOTSTRAP="localhost:9092"
export TOPIC="demo.orders"
python producer.py
```

Output:
```
Producing 10 messages to topic 'demo.orders' on localhost:9092
 -> sent key=order-1 to partition=0, offset=0
 -> sent key=order-2 to partition=0, offset=1
 ...
Done.
```

📥 2 – Consumer with CLI Arguments (consumer.py)

New consumer implementation with enhanced features:

Key Features:
- Command-line arguments for flexibility
- Consumer group support
- Offset tracking and reporting
- Environment variable configuration
- Auto-commit enabled
- Configurable offset reset (earliest/latest)

Code Structure:
```python
parser = argparse.ArgumentParser()
parser.add_argument("--group", default="group-a", help="Consumer group id")
parser.add_argument("--from-beginning", action="store_true",
                    help="Start at earliest offset")
args = parser.parse_args()

bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
topic = os.getenv("TOPIC", "demo.orders")

consumer = KafkaConsumer(
    topic,
    bootstrap_servers=bootstrap,
    group_id=args.group,
    enable_auto_commit=True,
    auto_offset_reset="earliest" if args.from_beginning else "latest",
    value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    key_deserializer=lambda b: b.decode("utf-8") if b else None,
    consumer_timeout_ms=10000,  # stop after idle
)
```

Offset Tracking:
The consumer displays committed offsets and next fetch positions per partition:
```python
for tp in consumer.assignment():
    committed = consumer.committed(tp)
    pos = consumer.position(tp)
    print(f"  {tp.topic}-{tp.partition}: committed={committed}, next_fetch={pos}")
```

Example Usage:
```bash
# Start from beginning with custom group
python consumer.py --group my-group --from-beginning

# Start from latest (default)
python consumer.py --group my-group
```

Output:
```
Consuming from topic 'demo.orders' as group 'my-group' (bootstrap=localhost:9092)
partition=0 offset=0 key=order-1 value={'id': 1, 'item': 'widget-1', ...}
partition=0 offset=1 key=order-2 value={'id': 2, 'item': 'widget-2', ...}

Committed offsets (approx positions) per partition:
  demo.orders-0: committed=2, next_fetch=2
```

🛠️ 3 – Management Scripts

Shell scripts for managing Kafka topics and consumer groups:

3.1 – Topic Creation (scripts/create_topic.sh)

Purpose: Create Kafka topics with configurable partitions and replication factor.

Features:
- Environment variable defaults (`KAFKA_BOOTSTRAP`, `TOPIC`, `PARTITIONS`, `REPLICATION`)
- Docker-based execution (runs inside Kafka container)
- `--if-not-exists` flag to prevent errors on re-runs
- Lists all topics after creation

Code:
```bash
BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP:-localhost:9092}"
TOPIC="${TOPIC:-demo.orders}"
PARTITIONS="${PARTITIONS:-3}"
REPLICATION="${REPLICATION:-1}"

docker exec kafka kafka-topics \
  --create \
  --if-not-exists \
  --topic "$TOPIC" \
  --partitions "$PARTITIONS" \
  --replication-factor "$REPLICATION" \
  --bootstrap-server "$BOOTSTRAP_SERVER"
```

Usage:
```bash
# Use defaults (demo.orders, 3 partitions, rf=1)
./scripts/create_topic.sh

# Custom topic
TOPIC="my.topic" PARTITIONS=6 REPLICATION=3 ./scripts/create_topic.sh
```

3.2 – Topic Description (scripts/describe_topic.sh)

Purpose: Display detailed information about a topic (partitions, replicas, ISR).

Usage:
```bash
TOPIC="demo.orders" ./scripts/describe_topic.sh
```

Output shows:
- Partition count
- Replication factor
- Leader broker for each partition
- In-sync replicas (ISR)
- Partition assignments

3.3 – Consumer Group Description (scripts/describe_group.sh)

Purpose: Monitor consumer group status, lag, and partition assignments.

Features:
- Auto-detects cluster mode (kafka-1, kafka-2, kafka-3) vs single mode (kafka)
- Uses internal listeners for cluster mode
- Shows partition assignments, offsets, and lag per consumer

Code:
```bash
# Auto-detect cluster or single mode
if docker ps --format '{{.Names}}' | grep -q '^kafka-1$'; then
  BOOTSTRAP_SERVER="kafka-1:19092,kafka-2:19092,kafka-3:19092"
  CONTAINER="kafka-1"
else
  BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP:-localhost:9092}"
  CONTAINER="kafka"
fi

GROUP="${1:-group-a}"
docker exec "$CONTAINER" /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server "$BOOTSTRAP_SERVER" \
  --group "$GROUP" \
  --describe
```

Usage:
```bash
# Describe default group
./scripts/describe_group.sh

# Describe specific group
./scripts/describe_group.sh my-consumer-group
```

Output columns:
- `PARTITION`: Partition number
- `CURRENT-OFFSET`: Last committed offset
- `LOG-END-OFFSET`: Latest available offset
- `LAG`: Difference (messages not yet consumed)
- `CONSUMER-ID`: Consumer instance ID

3.4 – List Consumer Groups (scripts/list_groups.sh)

Purpose: List all consumer groups in the cluster.

Usage:
```bash
./scripts/list_groups.sh
```

Output:
```
group-a
my-consumer-group
orders-cg
```

📊 4 – Technical Decisions & Adjustments

4.1 – Library Choice: kafka-python vs confluent-kafka

Original ChatGPT suggestion may have included `confluent-kafka`, but the implementation chose `kafka-python` because:
- No C dependencies (easier installation)
- Pure Python (better for debugging)
- Sufficient for basic producer-consumer use cases
- Better Pythonic API

Note: Later chapters may use `confluent-kafka` for advanced features (e.g., schema registry integration).

4.2 – Environment Variables

Configuration moved to environment variables for:
- Flexibility across environments (dev, staging, prod)
- Docker Compose integration
- CI/CD pipeline compatibility
- Security (no hardcoded credentials)

4.3 – Docker Integration

Scripts use `docker exec` to run Kafka CLI tools because:
- Kafka tools are bundled in the container
- No need to install Kafka CLI locally
- Consistent environment across team members
- Works with both single-node and cluster setups

4.4 – Offset Tracking

Consumer includes offset tracking to:
- Debug consumption issues
- Monitor progress
- Understand consumer state
- Verify auto-commit behavior

🔍 5 – File Structure

Files created/modified in this commit:

```
Python-Kafka-Proj/
├── consumer.py              # New: Consumer with CLI args and offset tracking
├── producer.py              # Refactored: Migrated to kafka-python
├── old_producer.py          # Kept for reference (confluent-kafka version)
└── scripts/
    ├── create_topic.sh      # New: Topic creation script
    ├── describe_topic.sh    # New: Topic inspection script
    ├── describe_group.sh    # New: Consumer group monitoring
    └── list_groups.sh       # New: List all consumer groups
```

🧪 6 – Testing the Setup

6.1 – Start Kafka:
```bash
docker-compose up -d
```

6.2 – Create Topic:
```bash
./scripts/create_topic.sh
```

6.3 – Start Consumer (Terminal 1):
```bash
python consumer.py --group test-group --from-beginning
```

6.4 – Produce Messages (Terminal 2):
```bash
python producer.py
```

6.5 – Monitor Consumer Group:
```bash
./scripts/describe_group.sh test-group
```

Expected Flow:
1. Producer sends 10 messages to `demo.orders`
2. Consumer receives and prints messages
3. Consumer shows committed offsets
4. `describe_group.sh` shows zero lag (all messages consumed)

🎯 7 – Key Concepts Introduced

| Concept | Description | Example |
|---------|-------------|---------|
| **Producer** | Client that publishes messages | `producer.py` |
| **Consumer** | Client that reads messages | `consumer.py` |
| **Topic** | Named channel for messages | `demo.orders` |
| **Consumer Group** | Collection of consumers sharing work | `group-a` |
| **Offset** | Position marker in a partition | `offset=5` |
| **Partition** | Subdivision of topic for parallelism | `partition=0` |
| **Bootstrap Server** | Entry point to discover Kafka cluster | `localhost:9092` |
| **Auto-commit** | Automatic offset commit after processing | `enable_auto_commit=True` |
| **Offset Reset** | Behavior when no committed offset exists | `earliest` or `latest` |

📝 8 – Summary

This chapter established the foundation for the Kafka project by:

✅ **Refactoring the producer** from `confluent-kafka` to `kafka-python` with environment-based configuration

✅ **Creating a flexible consumer** with CLI arguments, offset tracking, and consumer group support

✅ **Adding management scripts** for topic and consumer group operations

✅ **Implementing best practices** like environment variables, Docker integration, and offset monitoring

The setup provides a solid base for exploring more advanced Kafka features in subsequent chapters, such as:
- Multi-partition topics and consumer groups (Chapter 3)
- High-throughput producers
- Microservices integration
- Observability and monitoring

🚀 Next Steps

- **Chapter 2**: (If exists) Advanced producer configurations
- **Chapter 3**: Multi-partition topics & consumer groups
- Explore consumer group rebalancing
- Add error handling and retry logic
- Implement message schemas

---

*This chapter documents the initial commit: [feat: add Kafka consumer-producer setup with management scripts](https://github.com/Quraish05/learning-kafka/pull/1)*

