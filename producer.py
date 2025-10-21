"""
Kafka Producer for sending orders.
This module sends orders to the 'orders' topic.
"""
# pylint: disable=all
import json, os, time
from datetime import datetime
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

print(f"Producing 10 messages to topic '{TOPIC}' on {BOOTSTRAP}")
for i in range(1, 11):
    payload = {
        "id": i,
        "item": f"widget-{i}",
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    key = f"order-{i}"
    fut = producer.send(TOPIC, key=key, value=payload)
    md = fut.get(timeout=10)
    print(f" -> sent key={key} to partition={md.partition}, offset={md.offset}")
    time.sleep(0.05)

producer.flush()
producer.close()
print("Done.")
