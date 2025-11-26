🧩 Chapter 3 – Multi-Partition Topics & Consumer Groups

Goal:
Learn how to scale Kafka read/write throughput with multiple partitions, observe how consumer groups split work, and practice producing data fast enough to see these effects.

🏗 1 – Create a Multi-Partition Topic
Create the topic
docker exec -it kafka-1 bash

kafka-topics.sh \
  --create \
  --topic food.orders \
  --partitions 6 \
  --replication-factor 3 \
  --bootstrap-server kafka-1:9092,kafka-2:9092,kafka-3:9092

Verify
kafka-topics.sh --describe --topic food.orders --bootstrap-server kafka-1:9092


Example output

Topic: food.orders  PartitionCount: 6  ReplicationFactor: 3
  Partition: 0  Leader: 1  Replicas: 1,2,3  Isr: 1,2,3
  Partition: 1  Leader: 2  Replicas: 2,3,1  Isr: 2,3,1
  ...


📘 What this means

6 partitions → 6 lanes of parallelism.

Replication factor 3 → every message stored on 3 brokers.

Leader = broker handling writes for that partition.

ISR = “in-sync replicas” tracking that leader.

⚡ 2 – Fast Producer (producers/fast_order_producer.py)

A tuned producer that batches, compresses, and sends messages quickly.

Code overview
producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP.split(","),
    acks="all",              # Wait for leader + replicas
    linger_ms=20,            # Wait up to 20ms to batch
    batch_size=64*1024,      # 64 KiB buffer
    compression_type="lz4",  # Compress batches
)


linger_ms → micro-delay to batch messages (higher throughput).

batch_size → per-partition buffer before send.

acks="all" → safest durability mode.

compression_type → less network usage.

Run
COUNT=50000 python3 producers/fast_order_producer.py


Example output

Sent 50,000 messages to food.orders in 1.9s (25,590 msg/s).

Data flow diagram
graph LR
  subgraph Producer Client
    A[FastOrderProducer]
  end
  A -->|Batch + Compress| P0(Partition 0)
  A --> P1(Partition 1)
  A --> P2(Partition 2)
  A --> P3(Partition 3)
  A --> P4(Partition 4)
  A --> P5(Partition 5)

👥 3 – Consumer Group (consumers/group_order_consumer.py)

Each consumer in a group gets a subset of partitions.
Adding/removing consumers triggers a rebalance.

Start Alice
export KAFKA_BOOTSTRAP="localhost:9092,localhost:9094,localhost:9096"
export GROUP_ID="orders-cg"
export AUTO_OFFSET_RESET="earliest"
export CONSUMER_NAME="alice"
python3 consumers/group_order_consumer.py


Output

[alice] ASSIGNED: ['food.orders-0', ..., 'food.orders-5']
[alice] No messages received in 1000ms, continuing to poll...

Produce data in another terminal
COUNT=50000 python3 producers/fast_order_producer.py


Now Alice prints:

[alice] Message 1: food.orders-2 off=0 key=None value={...}
[alice] 5,000 msgs consumed (7,800/s). Last from food.orders-3 off=4999

Start Bob
GROUP_ID="orders-cg" CONSUMER_NAME="bob" \
python3 consumers/group_order_consumer.py


Observe rebalance:

[alice] REVOKED: [...]
[bob]   ASSIGNED: ['food.orders-1','food.orders-4','food.orders-5']
[alice] ASSIGNED: ['food.orders-0','food.orders-2','food.orders-3']

Visual model
graph TD
  subgraph Kafka Cluster (6 partitions)
    P0((0)):::p
    P1((1)):::p
    P2((2)):::p
    P3((3)):::p
    P4((4)):::p
    P5((5)):::p
  end
  subgraph Consumer Group "orders-cg"
    C1[Alice]
    C2[Bob]
  end
  P0 --> C1
  P1 --> C2
  P2 --> C1
  P3 --> C1
  P4 --> C2
  P5 --> C2
  classDef p fill:#eee,stroke:#999;

🍳 4 – Kitchen Workers (consumers/kitchen_worker.py)

A domain-flavored consumer that simulates “cooking”.

GROUP_ID="kitchen-cg" CONSUMER_NAME="kitchen-A" python3 consumers/kitchen_worker.py
GROUP_ID="kitchen-cg" CONSUMER_NAME="kitchen-B" python3 consumers/kitchen_worker.py


Output snippet

[kitchen-A] cooked seq=2997 from p1 off=3000
[kitchen-B] cooked seq=6002 from p4 off=6000


These behave like Alice + Bob but with per-order “processing” delays.

🔍 5 – Observe Partitions and Lag
CLI
docker exec -it kafka-1 bash \
  -c "kafka-consumer-groups.sh --describe --group orders-cg --bootstrap-server kafka-1:9092"


Shows for each partition:

PARTITION | CURRENT-OFFSET | LOG-END-OFFSET | LAG | CONSUMER-ID

🌐 6 – Visualise in UI

If you want to see rebalances and lag instead of reading CLI output:

Provectus Kafka-UI
docker run --rm -p 8080:8080 \
  -e KAFKA_CLUSTERS_0_NAME=local \
  -e KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS=host.docker.internal:9092,host.docker.internal:9094,host.docker.internal:9096 \
  provectuslabs/kafka-ui:latest


→ Open http://localhost:8080

Explore Topics and Consumer Groups (orders-cg) to watch members, partitions, and lag live.

Other options

Conduktor Console/Platform – polished desktop/web app.

Redpanda Console → docker run -p 8081:8080 redpandadata/console:latest.

AKHQ → docker run -p 8082:8080 tchiotludo/akhq:latest.

🧪 7 – Experiments
Experiment	What to Do	What You’ll See
Throughput vs Partitions	Change --partitions or keying strategy	Higher partitions = higher producer throughput
Rebalances	Start/stop Bob while Alice runs	Partitions reassigned live
Lag Monitoring	Produce a burst → watch lag drain	Lag increases then drains as consumers catch up
Key Hotspotting	Use one constant key	All messages on one partition → low throughput
🧠 8 – Concept Takeaways
Concept	Meaning
Partition	Unit of parallelism; ordering guaranteed within a partition
Replication Factor	Number of brokers storing the same data
Consumer Group	Parallel consumers that split partitions; each partition consumed by exactly one member
Offset	Position marker per partition
Lag	Difference between latest offset and committed offset
Rebalance	Process by which Kafka redistributes partitions when membership changes
🎯 End-of-Chapter Checklist

✅ Created a 6-partition topic
✅ Produced 50k orders (high throughput)
✅ Started two consumers and observed partition split
✅ Visualized lag & rebalances in a GUI

Next Chapter Idea:
Explore “Kafka as a backbone for microservices”—create a small FastAPI backend that publishes/consumes orders, then integrate observability (OpenTelemetry).