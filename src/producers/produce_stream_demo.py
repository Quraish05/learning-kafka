import json
import time
from uuid import uuid4
from confluent_kafka import Producer

TOPIC = "food.orders"
BOOTSTRAP_SERVERS = "localhost:9092"

def delivery_report(err, msg):
    if err is not None:
        print(f"[producer] Delivery failed: {err}")
    else:
        print(
            f"[producer] Delivered to {msg.topic()}[{msg.partition()}]@{msg.offset()} "
            f"key={msg.key()!r}"
        )

def main():
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})

    # These three events are chosen so you see alice -> bob -> alice
    demo_orders = [
        {
            "order_id": 1001,
            "user": "alice",
            "total": 399.0,
            "status": "PLACED",
            "ts": "2025-11-07T12:00:00Z",
        },
        {
            "order_id": 1002,
            "user": "bob",
            "total": 520.0,
            "status": "PLACED",
            "ts": "2025-11-07T12:01:00Z",
        },
        {
            "order_id": 1005,
            "user": "alice",
            "total": 199.0,
            "status": "PLACED",
            "ts": "2025-11-07T12:02:00Z",
        },
    ]

    for order in demo_orders:
        key = str(order["order_id"])
        value_bytes = json.dumps(order).encode("utf-8")

        print(f"[producer] Sending: {order}")
        producer.produce(
            topic=TOPIC,
            key=key,
            value=value_bytes,
            on_delivery=delivery_report,
        )


    # Force a flush to actually push out the messages
    producer.flush()
    print("[producer] Done sending demo orders.")

if __name__ == "__main__":
    main()