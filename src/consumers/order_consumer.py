
import os, json
from kafka import KafkaConsumer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("TOPIC", "food.orders")
GROUP = os.getenv("GROUP_ID", "orders-console")

def maybe_json(s):
    try:
        return json.loads(s)
    except Exception:
        return s  # plain string

if __name__ == "__main__":
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id=GROUP,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        value_deserializer=lambda b: b.decode("utf-8"),  # we get strings; parse manually
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
        consumer_timeout_ms=30000
    )

    print(f"[consumer] bootstrap={BOOTSTRAP} topic={TOPIC} group={GROUP}")
    for msg in consumer:
        data = maybe_json(msg.value)
        print(f"[consumer] partition={msg.partition} offset={msg.offset} key={msg.key} value={data}")