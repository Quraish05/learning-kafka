import os, json, time
from kafka import KafkaConsumer
from kafka.consumer.subscription_state import ConsumerRebalanceListener

# --- Config ---
# Provide all external listeners (host ports) as CSV in KAFKA_BOOTSTRAP
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092,localhost:9094,localhost:9096")
TOPIC = os.getenv("TOPIC", "food.orders")
GROUP = os.getenv("GROUP_ID", "orders-cg")

class RebalanceListener(ConsumerRebalanceListener):
    def __init__(self, name): self.name = name
    def on_partitions_assigned(self, consumer, partitions):
        parts = [f"{p.topic}-{p.partition}" for p in partitions]
        print(f"[{self.name}] ASSIGNED (callback): {parts}")
    def on_partitions_revoked(self, consumer, partitions):
        parts = [f"{p.topic}-{p.partition}" for p in partitions]
        print(f"[{self.name}] REVOKED: {parts}")
    def on_partitions_lost(self, consumer, partitions):
        parts = [f"{p.topic}-{p.partition}" for p in partitions]
        print(f"[{self.name}] LOST: {parts}")

def main():
    name = os.getenv("CONSUMER_NAME", f"c-{os.getpid()}")
    listener = RebalanceListener(name)

    consumer = KafkaConsumer(
        bootstrap_servers=[s.strip() for s in BOOTSTRAP.split(",") if s.strip()],
        group_id=GROUP,
        enable_auto_commit=True,
        auto_offset_reset=os.getenv("AUTO_OFFSET_RESET", "earliest"),
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,

        # sensible defaults; let kafka-python pick API version automatically
        request_timeout_ms=40000,              # fine to keep
        session_timeout_ms=30000,              # fine to keep
        consumer_timeout_ms=int(os.getenv("CONSUMER_TIMEOUT_MS", "0")),
        max_poll_records=int(os.getenv("MAX_POLL_RECORDS", "500")),
        fetch_max_bytes=int(os.getenv("FETCH_MAX_BYTES", str(50 * 1024 * 1024))),
    )

    print(f"[{name}] Subscribing to topic {TOPIC}...")
    consumer.subscribe([TOPIC], listener=listener)

    print(f"[{name}] Consuming {TOPIC} as group '{GROUP}' (bootstrap={BOOTSTRAP})")

    # ---- Wait until partitions are actually assigned ----
    assigned_wait_s = int(os.getenv("ASSIGN_WAIT_S", "10"))
    deadline = time.time() + assigned_wait_s
    while not consumer.assignment() and time.time() < deadline:
        consumer.poll(timeout_ms=500)  # triggers group join
    if consumer.assignment():
        parts = [f"{tp.topic}-{tp.partition}" for tp in consumer.assignment()]
        print(f"[{name}] ASSIGNED (checked): {parts}")
    else:
        print(f"[{name}] Still no assignment after {assigned_wait_s}s — check bootstrap/topic/group settings.")

    count, t0 = 0, time.time()
    poll_timeout = int(os.getenv("POLL_TIMEOUT_MS", "1000"))

    try:
        while True:
            message_batch = consumer.poll(timeout_ms=poll_timeout)
            if not message_batch:
                print(f"[{name}] No messages received in {poll_timeout}ms, continuing to poll...")
                continue

            for tp, messages in message_batch.items():
                for msg in messages:
                    count += 1
                    if count <= 5:
                        print(f"[{name}] Message {count}: {tp.topic}-{tp.partition} "
                              f"off={msg.offset} key={msg.key} value={msg.value}")
                    elif count % 5000 == 0:
                        dt = time.time() - t0
                        rate = count / dt if dt else count
                        print(f"[{name}] {count} msgs consumed ({rate:,.0f}/s). "
                              f"Last from {tp.topic}-{tp.partition} off={msg.offset}")
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        dt = time.time() - t0
        print(f"[{name}] Stopped. Total {count} msgs in {dt:.2f}s.")

if __name__ == "__main__":
    main()






