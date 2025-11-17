🧩 Chapter 2 – Multi-Broker Kafka Cluster with Partitioning and Failover

Goal:
Set up a production-ready multi-broker Kafka cluster with replication, partitioning, and fault tolerance. Learn how Kafka handles broker failures, partition leadership, and consumer group rebalancing.

📋 Overview

This chapter documents the second commit, which introduced a complete multi-broker Kafka cluster infrastructure with advanced features for handling partitioning and broker failures. The implementation includes:

- **3-broker Kafka cluster** using KRaft mode (no Zookeeper)
- **Replication and high availability** with replication factor 3 and min ISR 2
- **Service-specific topics** for a food ordering domain
- **Enhanced producer** with configurable acknowledgment levels
- **Consumer group demonstrations** for partition assignment visualization
- **Failover testing** to demonstrate automatic recovery

The implementation was guided by a ChatGPT conversation, with technical adjustments made based on practical testing and console/terminal history.

🏗️ 1 – Multi-Broker Cluster Setup (docker-compose.cluster.yml)

1.1 – Architecture Overview

The cluster consists of 3 Kafka brokers, each acting as both broker and controller (KRaft mode):

```
┌─────────────────────────────────────────────────────────┐
│              Kafka Cluster (KRaft Mode)                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│  │ kafka-1  │    │ kafka-2  │    │ kafka-3  │         │
│  │ :9092    │◄───┤ :9094    │◄───┤ :9096    │         │
│  │ (Leader) │    │          │    │          │         │
│  └──────────┘    └──────────┘    └──────────┘         │
│       │              │              │                   │
│       └──────────────┴──────────────┘                   │
│                    │                                    │
│              ┌──────────┐                              │
│              │ kafka-cli│                              │
│              │ (tools)  │                              │
│              └──────────┘                              │
└─────────────────────────────────────────────────────────┘
```

1.2 – Key Configuration Parameters

Each broker is configured with:

**KRaft Mode Settings:**
- `KAFKA_PROCESS_ROLES: broker,controller` - Each node acts as both broker and controller
- `KAFKA_CONTROLLER_QUORUM_VOTERS` - Defines the controller quorum (all 3 nodes)
- `KAFKA_CLUSTER_ID` - Shared cluster identifier across all brokers

**Listener Configuration:**
- `PLAINTEXT://:9092` - External listener (for clients from host)
- `CONTROLLER://:9093` - Controller listener (for KRaft quorum)
- `INTERNAL://:19092` - Internal listener (for inter-broker communication)

**High Availability Settings:**
- `KAFKA_DEFAULT_REPLICATION_FACTOR: 3` - Each partition replicated 3 times
- `KAFKA_MIN_INSYNC_REPLICAS: 2` - Minimum replicas that must acknowledge writes
- `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3` - Consumer offsets replicated 3 times

**Example Broker Configuration (kafka-1):**
```yaml
kafka-1:
  image: apache/kafka:latest
  container_name: kafka-1
  ports: ["9092:9092"]
  environment:
    KAFKA_NODE_ID: 1
    KAFKA_PROCESS_ROLES: broker,controller
    KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093"
    KAFKA_LISTENERS: "PLAINTEXT://:9092,CONTROLLER://:9093,INTERNAL://:19092"
    KAFKA_ADVERTISED_LISTENERS: "PLAINTEXT://localhost:9092,INTERNAL://kafka-1:19092"
    KAFKA_INTER_BROKER_LISTENER_NAME: INTERNAL
    KAFKA_DEFAULT_REPLICATION_FACTOR: 3
    KAFKA_MIN_INSYNC_REPLICAS: 2
  volumes: ["kafka1_data:/var/lib/kafka/data"]
```

1.3 – Why KRaft Mode?

KRaft (Kafka Raft) replaces Zookeeper for metadata management:
- **Simpler architecture** - No separate Zookeeper cluster needed
- **Better performance** - Faster controller failover
- **Scalability** - Supports larger clusters
- **Modern standard** - Recommended for new deployments

1.4 – Listener Types Explained

| Listener | Port | Purpose | Used By |
|----------|------|---------|---------|
| **PLAINTEXT** | 9092/9094/9096 | External client connections | Producers, consumers from host |
| **CONTROLLER** | 9093 | KRaft quorum communication | Controllers for metadata |
| **INTERNAL** | 19092 | Inter-broker replication | Brokers for data replication |

**Why separate listeners?**
- **Security**: Different protocols/authentication per listener
- **Network isolation**: Internal traffic stays within Docker network
- **Performance**: Optimize each listener for its use case

1.5 – Starting the Cluster

```bash
# Start all 3 brokers
docker compose -f docker-compose.cluster.yml up -d

# Verify all brokers are running
docker ps | grep kafka
```

Expected output:
```
kafka-1    Up   0.0.0.0:9092->9092/tcp
kafka-2    Up   0.0.0.0:9094->9092/tcp
kafka-3    Up   0.0.0.0:9096->9092/tcp
kafka-cli  Up   (tools container)
```

🔧 2 – Makefile for Cluster Management

The Makefile provides convenient commands for common operations:

```makefile
cluster-up:    # Start the cluster
topics:        # Create food service topics
health:        # Check cluster health
failover:      # Demonstrate broker failure recovery
produce:       # Produce test messages
consume-one:   # Consume with a single consumer
```

**Usage:**
```bash
# Start cluster
make cluster-up

# Create topics
make topics

# Check health
make health

# Test failover
make failover

# Produce messages
make produce

# Consume messages
make consume-one
```

📝 3 – Topic Creation Scripts

3.1 – Food Service Topics (scripts/create-food-topics.sh)

Creates topics for a food ordering domain:

**Topics Created:**
- `demo.orders` - Order events (3 partitions, RF=3)
- `demo.payments` - Payment events (3 partitions, RF=3)
- `demo.restaurant` - Restaurant events (3 partitions, RF=3)
- `demo.delivery` - Delivery events (3 partitions, RF=3)

**Script Logic:**
```bash
topics=(
  "demo.orders:3:3"      # name:partitions:replication-factor
  "demo.payments:3:3"
  "demo.restaurant:3:3"
  "demo.delivery:3:3"
)

for t in "${topics[@]}"; do
  IFS=':' read -r name parts rf <<< "$t"
  docker compose -f docker-compose.cluster.yml exec -T kafka-cli \
    /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server "kafka-1:19092" \
    --create --if-not-exists \
    --topic "$name" \
    --partitions "$parts" \
    --replication-factor "$rf"
done
```

**Key Points:**
- Uses **INTERNAL listener** (`kafka-1:19092`) for cluster communication
- `--if-not-exists` prevents errors on re-runs
- All topics have **3 partitions** for parallelism
- **Replication factor 3** ensures high availability

**Why 3 partitions?**
- Allows up to 3 consumers in a group (one per partition)
- Provides parallelism for processing
- Balances throughput with complexity

**Why replication factor 3?**
- Can tolerate 1 broker failure (2 replicas remain)
- Meets min ISR requirement (2 replicas must be in-sync)
- Standard for production clusters

3.2 – Verifying Topics

```bash
# List all topics
docker compose -f docker-compose.cluster.yml exec kafka-cli \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka-1:19092 --list

# Describe a topic
docker compose -f docker-compose.cluster.yml exec kafka-cli \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka-1:19092 --describe --topic demo.orders
```

**Example Output:**
```
Topic: demo.orders  PartitionCount: 3  ReplicationFactor: 3
  Partition: 0  Leader: 1  Replicas: 1,2,3  Isr: 1,2,3
  Partition: 1  Leader: 2  Replicas: 2,3,1  Isr: 2,3,1
  Partition: 2  Leader: 3  Replicas: 3,1,2  Isr: 3,1,2
```

**Understanding the Output:**
- **Leader**: Broker handling reads/writes for this partition
- **Replicas**: All brokers storing this partition
- **Isr** (In-Sync Replicas): Replicas that are up-to-date with the leader

🔍 4 – Cluster Health Monitoring (scripts/cluster-health.sh)

Monitors cluster metadata and topic status:

**What it checks:**
1. **Metadata quorum status** - Controller health
2. **Topic description** - Partition leadership and ISR

**Script:**
```bash
echo "===== Metadata quorum status ====="
docker compose -f docker-compose.cluster.yml exec -T kafka-cli \
  /opt/kafka/bin/kafka-metadata-quorum.sh \
  --bootstrap-server kafka-1:19092 describe --status

echo "===== demo.orders description ====="
docker compose -f docker-compose.cluster.yml exec -T kafka-cli \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka-1:19092 --describe --topic demo.orders
```

**Quorum Status Output:**
```
ClusterId:              V2qC2jqgQ1m8iG4u5p7qA
LeaderId:               1
LeaderEpoch:            0
HighWatermark:          123
MaxFollowerLag:         0
MaxFollowerLagTimeMs:   0
CurrentVoters:          [1, 2, 3]
Observers:              []
```

**What to look for:**
- ✅ All brokers in `CurrentVoters`
- ✅ `MaxFollowerLag: 0` (all replicas in sync)
- ✅ Leader is elected and stable

⚡ 5 – Enhanced Producer (src/producer_partitioned.py)

5.1 – Configurable Acknowledgments

The producer supports different ACK levels for durability vs performance trade-offs:

```python
parser.add_argument("--acks", default="all", choices=["0","1","all"])
```

**ACK Levels:**

| ACK Level | Behavior | Use Case | Risk |
|-----------|----------|----------|------|
| **0** | Fire-and-forget | High throughput, loss acceptable | Data loss possible |
| **1** | Wait for leader | Balanced performance/durability | Data loss if leader fails before replication |
| **all** | Wait for leader + ISR | Maximum durability | Slower but safest |

**Code:**
```python
producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP,
    acks=args.acks,             # "0", "1", or "all"
    retries=10,
    linger_ms=10,
    key_serializer=lambda s: s.encode("utf-8"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)
```

5.2 – Key-Based Partitioning

Messages are partitioned by key to ensure related messages go to the same partition:

```python
order_id, payload = make_order()
fut = producer.send(TOPIC, key=order_id, value=payload, headers=[("event-type", b"order-created")])
md = fut.get(timeout=10)
print(f"Sent order {payload['order_id']} -> partition {md.partition}, offset {md.offset}")
```

**Why use keys?**
- **Ordering guarantee**: Messages with same key go to same partition
- **Consumer locality**: Related messages processed by same consumer
- **Predictable routing**: Easier to debug and monitor

**Key Hashing:**
Kafka uses `murmur2` hash of the key to determine partition:
```
partition = hash(key) % num_partitions
```

5.3 – Message Headers

Headers allow adding metadata without modifying the message value:

```python
headers=[("event-type", b"order-created")]
```

**Use cases:**
- Event type classification
- Tracing IDs (OpenTelemetry)
- Schema version
- Source service identifier

5.4 – Usage Examples

```bash
# Produce with acks=all (safest)
python3 -m src.producer_partitioned --count 30 --delay 0.1 --acks all

# Produce with acks=1 (faster)
python3 -m src.producer_partitioned --count 100 --delay 0.05 --acks 1

# Produce with acks=0 (fastest, but may lose messages)
python3 -m src.producer_partitioned --count 1000 --delay 0.01 --acks 0
```

👥 6 – Consumer Group Demo (src/consumer_group_demo.py)

6.1 – Group-Aware Consumer

Demonstrates partition assignment and offset tracking:

**Features:**
- Configurable consumer group
- Offset reset behavior (earliest/latest)
- Detailed message metadata logging
- Header extraction and display

**Code:**
```python
consumer = KafkaConsumer(
    args.topic,
    bootstrap_servers=bootstrap,
    group_id=args.group,
    enable_auto_commit=True,
    auto_offset_reset="earliest" if args.from_beginning else "latest",
    value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    key_deserializer=lambda b: b.decode("utf-8") if b else None,
    consumer_timeout_ms=0,  # Wait indefinitely
)
```

**Message Logging:**
```python
for msg in consumer:
    headers = {k: (v.decode() if v else None) for (k, v) in (msg.headers or [])}
    print(
        f"[{args.group}] p={msg.partition} off={msg.offset} key={msg.key} "
        f"value={msg.value} headers={headers}"
    )
```

6.2 – Observing Rebalancing

**Start Consumer 1:**
```bash
python3 -m src.consumer_group_demo --group group-a --from-beginning
```

**Start Consumer 2 (in another terminal):**
```bash
python3 -m src.consumer_group_demo --group group-a --from-beginning
```

**What happens:**
1. Consumer 1 gets all 3 partitions initially
2. Consumer 2 joins the group
3. Kafka triggers a **rebalance**
4. Partitions are redistributed (e.g., Consumer 1 gets partitions 0,1; Consumer 2 gets partition 2)

**Rebalancing Phases:**
1. **Revoke** - Consumers release their partitions
2. **Assign** - Kafka redistributes partitions
3. **Resume** - Consumers start consuming from new assignments

🏪 7 – Service-Specific Consumers

7.1 – Architecture Pattern

Each microservice has its own consumer group, allowing multiple services to process the same topic independently:

```
┌─────────────────┐
│  demo.orders    │
│   (Topic)       │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬─────────────┐
    │         │          │             │
┌───▼───┐ ┌──▼───┐  ┌───▼────┐  ┌────▼────┐
│Kitchen│ │Payment│  │Delivery│  │Analytics│
│Service│ │Service│  │Service │  │Service  │
└───────┘ └───────┘  └────────┘  └─────────┘
Group:    Group:     Group:       Group:
kitchen   payments   delivery     analytics
```

**Benefits:**
- **Independent processing** - Each service processes at its own pace
- **No interference** - Services don't affect each other's offsets
- **Scalability** - Each service can scale its consumers independently

7.2 – Kitchen Consumer (src/consumers/kitchen_consumer.py)

```python
topic = "demo.orders"
group = "kitchen-service"

consumer = KafkaConsumer(
    topic,
    bootstrap_servers=bootstrap,
    group_id=group,
    enable_auto_commit=True,
    auto_offset_reset="latest",  # Only new orders
    value_deserializer=lambda b: json.loads(b.decode("utf-8")),
)
```

**Behavior:**
- Consumes from `demo.orders`
- Consumer group: `kitchen-service`
- Starts from `latest` (only processes new orders)
- Can have multiple kitchen workers in the same group

7.3 – Payments Consumer (src/consumers/payments_consumer.py)

```python
topic = "demo.orders"
group = "payments-service-v2"

consumer = KafkaConsumer(
    topic,
    bootstrap_servers=bootstrap,
    group_id=group,
    enable_auto_commit=True,
    auto_offset_reset="earliest",  # Process all orders
    value_deserializer=lambda b: json.loads(b.decode("utf-8")),
)
```

**Behavior:**
- Consumes from `demo.orders`
- Consumer group: `payments-service-v2`
- Starts from `earliest` (processes historical orders)
- Useful for backfilling or reprocessing

7.4 – Delivery Consumer (src/consumers/delivery_consumer.py)

Similar structure to kitchen consumer, with `delivery-service` group.

**Running Multiple Services:**
```bash
# Terminal 1: Kitchen service
python3 src/consumers/kitchen_consumer.py

# Terminal 2: Payments service
python3 src/consumers/payments_consumer.py

# Terminal 3: Delivery service
python3 src/consumers/delivery_consumer.py

# Terminal 4: Produce orders
python3 -m src.producer_partitioned --count 50
```

All three services will process the same messages independently!

💥 8 – Failover Demonstration (scripts/demo-failover.sh)

8.1 – Testing Broker Failure

The script simulates a broker failure and demonstrates automatic recovery:

**Steps:**
1. Stop broker kafka-2
2. Check topic description (new leaders assigned)
3. Restart broker kafka-2
4. Verify ISR recovery

**Script:**
```bash
echo "Stopping broker kafka-2 to simulate failure..."
docker compose -f docker-compose.cluster.yml stop kafka-2
sleep 5

echo "Describe topic to see new leaders/ISR after failover:"
docker compose -f docker-compose.cluster.yml exec -T kafka-cli \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka-1:19092 --describe --topic demo.orders

echo "Restarting broker kafka-2..."
docker compose -f docker-compose.cluster.yml start kafka-2
sleep 8

echo "Describe topic again (ISR should recover):"
docker compose -f docker-compose.cluster.yml exec -T kafka-cli \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka-1:19092 --describe --topic demo.orders
```

8.2 – Before Failure

```
Partition: 0  Leader: 1  Replicas: 1,2,3  Isr: 1,2,3
Partition: 1  Leader: 2  Replicas: 2,3,1  Isr: 2,3,1
Partition: 2  Leader: 3  Replicas: 3,1,2  Isr: 3,1,2
```

8.3 – After kafka-2 Stops

```
Partition: 0  Leader: 1  Replicas: 1,2,3  Isr: 1,3      # 2 removed from ISR
Partition: 1  Leader: 3  Replicas: 2,3,1  Isr: 3,1      # Leader changed from 2→3
Partition: 2  Leader: 3  Replicas: 3,1,2  Isr: 3,1      # 2 removed from ISR
```

**What happened:**
- Partition 1's leader (broker 2) failed
- Kafka elected broker 3 as new leader
- ISR updated to exclude broker 2
- **No data loss** - All data still available on replicas

8.4 – After kafka-2 Recovers

```
Partition: 0  Leader: 1  Replicas: 1,2,3  Isr: 1,2,3    # 2 rejoined ISR
Partition: 1  Leader: 3  Replicas: 2,3,1  Isr: 3,1,2     # 2 catching up
Partition: 2  Leader: 3  Replicas: 3,1,2  Isr: 3,1,2     # 2 rejoined ISR
```

**Recovery process:**
1. Broker 2 starts and contacts the leader
2. Leader sends missing messages to broker 2
3. Broker 2 catches up and rejoins ISR
4. Cluster returns to full health

8.5 – Producer Behavior During Failover

**With `acks="all"`:**
- Producer waits for min ISR (2 replicas) to acknowledge
- If min ISR not met, producer may retry or fail
- Ensures durability even during failures

**With `acks=1`:**
- Producer only waits for leader acknowledgment
- Faster but less safe during failures
- May lose data if leader fails before replication

**Testing:**
```bash
# Produce during failover
make failover &
python3 -m src.producer_partitioned --count 100 --acks all
```

Observe how the producer handles the failure and recovery.

📊 9 – Key Concepts

| Concept | Description | Example |
|---------|-------------|---------|
| **Broker** | Kafka server node | kafka-1, kafka-2, kafka-3 |
| **KRaft** | Metadata management without Zookeeper | Modern Kafka mode |
| **Replication Factor** | Number of copies of each partition | RF=3 means 3 copies |
| **ISR** | In-Sync Replicas (up-to-date copies) | ISR: 1,2,3 |
| **Min ISR** | Minimum replicas that must acknowledge writes | min.insync.replicas=2 |
| **Leader** | Broker handling reads/writes for a partition | Leader: 1 |
| **Follower** | Replica that copies from leader | Replicas: 1,2,3 |
| **Partition** | Subdivision of topic for parallelism | Partition: 0, 1, 2 |
| **Consumer Group** | Collection of consumers sharing work | kitchen-service |
| **Rebalance** | Redistribution of partitions when consumers join/leave | Automatic process |
| **ACK Level** | Producer acknowledgment requirement | 0, 1, or all |

🔐 10 – High Availability Guarantees

**With RF=3 and min ISR=2:**

| Scenario | Impact | Availability |
|----------|--------|--------------|
| 1 broker fails | 2 replicas remain | ✅ Available (meets min ISR) |
| 2 brokers fail | 1 replica remains | ❌ Unavailable (below min ISR) |
| All brokers fail | 0 replicas | ❌ Unavailable |

**Trade-offs:**
- **Higher RF** = Better durability, more storage, slower writes
- **Lower min ISR** = Faster writes, less durability guarantee
- **Production recommendation**: RF=3, min ISR=2 (tolerates 1 failure)

🧪 11 – Testing the Complete Setup

11.1 – Full Workflow

```bash
# 1. Start cluster
make cluster-up

# 2. Create topics
make topics

# 3. Check health
make health

# 4. Produce messages (Terminal 1)
make produce

# 5. Consume with group-a (Terminal 2)
make consume-one

# 6. Start service consumers (Terminals 3-5)
python3 src/consumers/kitchen_consumer.py
python3 src/consumers/payments_consumer.py
python3 src/consumers/delivery_consumer.py

# 7. Test failover
make failover
```

11.2 – Monitoring Consumer Groups

```bash
# List all consumer groups
docker compose -f docker-compose.cluster.yml exec kafka-cli \
  /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server kafka-1:19092 --list

# Describe a specific group
docker compose -f docker-compose.cluster.yml exec kafka-cli \
  /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server kafka-1:19092 \
  --group kitchen-service --describe
```

**Output shows:**
- Partition assignments
- Current offsets
- Lag (messages behind)
- Consumer IDs

📝 12 – File Structure

Files created/modified in this commit:

```
Python-Kafka-Proj/
├── docker-compose.cluster.yml    # New: 3-broker cluster config
├── Makefile                      # New: Cluster management commands
├── scripts/
│   ├── create-food-topics.sh    # New: Topic creation for food domain
│   ├── cluster-health.sh        # New: Health monitoring
│   └── demo-failover.sh         # New: Failover demonstration
└── src/
    ├── producer_partitioned.py  # New: Enhanced producer with ACK levels
    ├── consumer_group_demo.py   # New: Group-aware consumer demo
    └── consumers/
        ├── delivery_consumer.py # New: Delivery service consumer
        ├── kitchen_consumer.py  # New: Kitchen service consumer
        └── payments_consumer.py # New: Payments service consumer
```

🎯 13 – Summary

This chapter established a production-ready Kafka cluster by:

✅ **Setting up a 3-broker cluster** with KRaft mode for high availability

✅ **Configuring replication** (RF=3, min ISR=2) to tolerate broker failures

✅ **Creating service-specific topics** for a food ordering domain

✅ **Implementing enhanced producer** with configurable ACK levels for durability trade-offs

✅ **Demonstrating consumer groups** with multiple service consumers

✅ **Testing failover** to verify automatic recovery from broker failures

✅ **Providing management tools** (Makefile, scripts) for cluster operations

**Key Takeaways:**
- Multi-broker clusters provide fault tolerance and scalability
- Replication ensures data durability even during failures
- Consumer groups allow multiple services to process the same topic independently
- KRaft mode simplifies cluster management (no Zookeeper)
- Proper ACK configuration balances performance and durability

🚀 Next Steps

- **Chapter 3**: Multi-partition topics & consumer groups (already documented)
- Explore consumer group rebalancing in detail
- Add monitoring and alerting
- Implement schema registry for message validation
- Add authentication and authorization (SASL/SSL)

---

*This chapter documents the second commit: [chp-2:feat: created multi broker Kafka cluster, topic creation for service domains, Health, Failure, Service specific Consumers](https://github.com/Quraish05/learning-kafka/pull/2)*

