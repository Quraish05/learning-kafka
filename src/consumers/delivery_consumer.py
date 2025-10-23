# src/consumers/delivery_consumer.py
import os, json
from kafka import KafkaConsumer

bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
topic = "demo.orders"
group = "delivery-service"

consumer = KafkaConsumer(
    topic,
    bootstrap_servers=bootstrap,
    group_id=group,
    enable_auto_commit=True,
    auto_offset_reset="latest",
    value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    key_deserializer=lambda b: b.decode("utf-8") if b else None,
)

print(f"[{group}] listening on {topic}")
for msg in consumer:
    order = msg.value
    print(f"[{group}] charged order {order['order_id']} (p{msg.partition}/o{msg.offset})")
