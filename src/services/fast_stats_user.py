import json
import threading
from typing import Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from confluent_kafka import Producer, Consumer, KafkaError
from confluent_kafka.serialization import (
    StringSerializer,
    SerializationContext,
    MessageField,
)
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from opentelemetry import trace
from .order_models import OrderIn


# OpenTelemetry tracer (global)
tracer = trace.get_tracer("app.fastapi")

# Kafka config (adjust if your ports are different)
BOOTSTRAP_SERVERS = "localhost:9092"
ORDERS_TOPIC = "food.orders"
STATS_TOPIC = "food.orders.by_user"
ORDERS_TOPIC_AVRO = "food.orders.avro"
SCHEMA_REGISTRY_URL = "http://localhost:8081"

# Avro schema for Order
ORDER_SCHEMA_STR = """
{
  "type": "record",
  "name": "Order",
  "namespace": "food",
  "fields": [
    {"name": "order_id", "type": "int"},
    {"name": "user",     "type": "string"},
    {"name": "total",    "type": "double"},
    {"name": "status",   "type": "string"},
    {"name": "ts",       "type": "string"}
  ]
}
"""


def order_to_dict(order, ctx):
    # We'll use plain dicts, so this is just identity
    return order

# Schema Registry client + Avro serializer
schema_registry_conf = {"url": SCHEMA_REGISTRY_URL}
schema_registry_client = SchemaRegistryClient(schema_registry_conf)

avro_value_serializer = AvroSerializer(
    schema_registry_client=schema_registry_client,
    schema_str=ORDER_SCHEMA_STR,
    to_dict=order_to_dict,
)

key_serializer = StringSerializer("utf_8")


# Global in-memory cache for user stats (user -> count)
user_counts: Dict[str, int] = {}
user_counts_lock = threading.Lock()

# Kafka Producer instance (for /orders)
producer_conf = {
    "bootstrap.servers": BOOTSTRAP_SERVERS,
    "client.id": "fastapi-orders-producer",
}
producer = Producer(producer_conf)


def delivery_report(err, msg):
    # Called by Producer for each message to report success/failure.
    # Runs in the Producer's IO thread.
    if err is not None:
        # In real code you'd use logging instead of print
        print(f"[producer] Delivery failed: {err}")
    else:
        print(
            f"[producer] Delivered to {msg.topic()}[{msg.partition()}]@{msg.offset()} "
            f"key={msg.key()!r}"
        )


# FastAPI app
app = FastAPI(
    title="Kafka Food Orders API",
    version="0.1.0",
)


@app.post("/orders")
async def place_order(order: OrderIn):
    # Place an order:
    # Build an order JSON with ID, user, total, status.
    # Produce it to Kafka topic `food.orders`.
    # For demo: simple, increasing-ish ID based on length of cache (you can replace with real UUID)
    order_id = len(user_counts) + 1

    order_event = {
        "order_id": order_id,
        "user": order.user,
        "total": order.total,
        "status": order.status,
        "ts": "2025-11-07T12:34:56Z",  # in real code, use datetime.utcnow().isoformat()
    }

    value_bytes = json.dumps(order_event).encode("utf-8")
    key_str = str(order_id)

    try:
        # Asynchronous send
        producer.produce(
            topic=ORDERS_TOPIC,
            key=key_str,
            value=value_bytes,
            on_delivery=delivery_report,
        )
        # Trigger delivery callbacks for queued messages
        producer.poll(0)
    except BufferError as e:
        # Producer queue is full or some other error
        raise HTTPException(status_code=500, detail=f"Kafka buffer error: {e}")

    print(f"[api] Queued order event: {order_event}")

    return {
        "message": "Order accepted for processing",
        "order": order_event,
    }


@app.get("/stats/users/{user}")
async def get_user_stats(user: str):
    # Return the latest known order count for a given user,
    # as maintained by the Faust stream processor (via Kafka stats topic).
    with user_counts_lock:
        count = user_counts.get(user)

    if count is None:
        # We haven't seen this user in the stats stream yet
        return {"user": user, "order_count": 0, "note": "No orders processed yet"}

    return {"user": user, "order_count": count}


# Background consumer to keep user_counts up to date

def _stats_consumer_loop():
    # Runs in a separate thread.
    # Subscribes to `food.orders.by_user`, and updates user_counts dict
    # whenever a new aggregate is emitted by the Faust app.
    consumer_conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": "fastapi-stats-reader",
        "auto.offset.reset": "earliest",
    }
    consumer = Consumer(consumer_conf)
    consumer.subscribe([STATS_TOPIC])

    print("[stats-consumer] Started, subscribed to", STATS_TOPIC)

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # End of partition event, harmless
                    continue
                print(f"[stats-consumer] Error: {msg.error()}")
                continue

            # key is user, value is the count (as bytes)
            user_key = msg.key().decode("utf-8") if msg.key() else None
            value_str = msg.value().decode("utf-8") if msg.value() else "0"

            try:
                new_count = int(value_str)
            except ValueError:
                print(
                    f"[stats-consumer] Could not parse count from value: {value_str!r}")
                continue

            if user_key:
                with user_counts_lock:
                    user_counts[user_key] = new_count

                print(
                    f"[stats-consumer] Updated count: user={user_key} "
                    f"count={new_count} (offset={msg.offset()})"
                )
    finally:
        consumer.close()
        print("[stats-consumer] Closed.")


@app.on_event("startup")
def start_background_stats_consumer():
    # On FastAPI startup, launch the stats consumer in a daemon thread.
    t = threading.Thread(target=_stats_consumer_loop, daemon=True)
    t.start()
    print("[api] Background stats consumer thread started")
