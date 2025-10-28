import json, os, time, uuid, random
from datetime import datetime
from kafka import KafkaProducer

### Config (via env or defaults)
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("TOPIC", "food.orders")

# Throughput tuning knobs:
# linger_ms: wait up to N ms to batch more messages before a send (bigger batches = better throughput)
LINGER_MS = int(os.getenv("LINGER_MS", "20"))

# batch_size: max bytes per batch (producer-side buffer). Larger = fewer requests (better throughput).
BATCH_SIZE = int(os.getenv("BATCH_SIZE", str(64*1024)))  # 64 KiB

# compression_type: compresses batches over the wire (less bandwidth, better throughput on network)
COMPRESSION = os.getenv("COMPRESSION", "lz4")  # alt: gzip, snappy, zstd

### Producer construction
# KafkaProducer manages:
# a background IO thread that sends RecordBatches to the leader of each partition
# retries (depending on acks/error) and batch buffering
producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP.split(","),   # list of brokers to discover the cluster
    acks="all",                               # wait until the leader+ISR have the record (stronger durability)
    linger_ms=LINGER_MS,                      # allow a small window to coalesce messages into batches
    batch_size=BATCH_SIZE,                    # target max batch size (bytes)
    compression_type=COMPRESSION,             # compress batches before sending
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),   # convert dict -> JSON bytes
    key_serializer=lambda k: k.encode("utf-8") if k else None,  # convert str key -> bytes
)

def make_order(i:int):
    # Sample "domain" payload for our food app
    return {
        "order_id": str(uuid.uuid4()),
        "seq": i,
        "restaurant": random.choice(["Tandoori Tales", "Pizza Hub", "Bao Bae", "Masala Magic"]),
        "items": random.sample(
            ["biryani","pizza","wings","bao","dosa","burger","chaat"], k=random.randint(1,3)
        ),
        "total": round(random.uniform(5, 35), 2),
        "ts": datetime.utcnow().isoformat()
    }

def main():
    # COUNT: how many messages to send
    n = int(os.getenv("COUNT", "50000"))

    # USE_KEYS=false → unkeyed → the client’s partitioner spreads across partitions (good parallelism).
    # USE_KEYS=true  → supply many distinct keys so the hash spreads across partitions deterministically.
    use_keys = os.getenv("USE_KEYS", "false").lower() == "true"
    keys_space = [f"k{i}" for i in range(32)]  # 32 distinct keys => typically well spread across 6 partitions

    t0 = time.time()
    futures = []  # send() returns a FutureRecordMetadata; we could inspect for per-record ack if desired

    for i in range(n):
        order = make_order(i)
        key = random.choice(keys_space) if use_keys else None

        # send() is async; messages are enqueued into batches by partition; background thread sends them.
        futures.append(producer.send(TOPIC, key=key, value=order))

        # Optional flush cadence to bound memory during huge runs:
        if i % 5000 == 0 and i > 0:
            producer.flush()  # blocks until all enqueued messages are sent/acked

    # Ensure all messages are out before timing
    producer.flush()

    dt = time.time() - t0
    rate = n / dt if dt else n
    print(f"Sent {n} messages to {TOPIC} in {dt:.2f}s ({rate:,.0f} msg/s).")

if __name__ == "__main__":
    main()