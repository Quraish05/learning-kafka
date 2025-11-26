# src/services/fast_stats_user_avro.py

import threading
from typing import Dict

from fastapi import FastAPI, HTTPException
from opentelemetry import trace

from confluent_kafka import Producer, Consumer, KafkaError
from confluent_kafka.serialization import (
    StringSerializer,
    SerializationContext,
    MessageField,
)
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.schema_registry.error import SchemaRegistryError

from .order_models import OrderIn  # shared with non-Avro version

# Import connection error types from urllib3/requests (used by schema registry client)
try:
    from requests.exceptions import ConnectionError as RequestsConnectionError
except ImportError:
    try:
        from urllib3.exceptions import NewConnectionError as RequestsConnectionError
    except ImportError:
        RequestsConnectionError = type(None)  # Use a type that will never match

# OpenTelemetry tracer
tracer = trace.get_tracer("app.fastapi.avro")

# Kafka / Schema Registry config (Avro pipeline)
BOOTSTRAP_SERVERS = "localhost:9092"
ORDERS_TOPIC = "food.orders.avro"         # Avro orders topic (separate from JSON pipeline)
STATS_TOPIC = "food.orders.by_user_avro"  # Avro pipeline's stats topic
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
    # We use plain dicts as our Python type, so this is identity
    return order

# Schema Registry + Avro serializer
schema_registry_conf = {"url": SCHEMA_REGISTRY_URL}
schema_registry_client = SchemaRegistryClient(schema_registry_conf)

avro_value_serializer = AvroSerializer(
    schema_registry_client=schema_registry_client,
    schema_str=ORDER_SCHEMA_STR,
    to_dict=order_to_dict,
)

key_serializer = StringSerializer("utf_8")

# In-memory stats cache for Avro pipeline
user_counts: Dict[str, int] = {}
user_counts_lock = threading.Lock()

# Kafka Producer for /orders (Avro)
producer_conf = {
    "bootstrap.servers": BOOTSTRAP_SERVERS,
    "client.id": "fastapi-orders-producer-avro",
}
producer = Producer(producer_conf)


def delivery_report(err, msg):
    if err is not None:
        print(f"[producer-avro] Delivery failed: {err}")
    else:
        print(
            f"[producer-avro] Delivered to {msg.topic()}[{msg.partition()}]@{msg.offset()} "
            f"key={msg.key()!r}"
        )


# FastAPI app (Avro version)
app = FastAPI(
    title="Kafka Food Orders API (Avro)",
    version="0.1.0",
)

@app.get("/health")
async def health_check():
    """Health check endpoint to verify Kafka and Schema Registry connectivity"""
    health_status = {
        "status": "healthy",
        "kafka": "unknown",
        "schema_registry": "unknown"
    }
    
    # Check Kafka connectivity
    try:
        producer.poll(0)
        health_status["kafka"] = "connected"
    except Exception as e:
        health_status["kafka"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check Schema Registry connectivity
    try:
        schema_registry_client.get_subjects()
        health_status["schema_registry"] = "connected"
    except Exception as e:
        health_status["schema_registry"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return health_status

@app.get("/test-schema-registry")
async def test_schema_registry():
    """Test endpoint to diagnose Schema Registry connectivity"""
    try:
        subjects = schema_registry_client.get_subjects()
        return {
            "status": "connected",
            "subjects": subjects,
            "url": SCHEMA_REGISTRY_URL
        }
    except Exception as e:
        error_type = type(e).__name__
        error_str = str(e)
        error_module = type(e).__module__
        return {
            "status": "error",
            "error_type": error_type,
            "error_module": error_module,
            "error_message": error_str,
            "url": SCHEMA_REGISTRY_URL
        }

@app.post("/orders-avro")
async def place_order_avro(order: OrderIn):
    """
    Place an order (Avro version):
      Build an order dict
      Serialize as Avro with Schema Registry
      Produce to Kafka topic `food.orders.avro`
      Wrap the Kafka call in an OTel span
    """
    with user_counts_lock:
        next_id = len(user_counts) + 1
    order_id = next_id

    order_event = {
        "order_id": order_id,
        "user": order.user,
        "total": float(order.total),
        "status": order.status,
        "ts": "2025-11-07T12:34:56Z",  # in real code, use datetime.utcnow().isoformat()
    }


    with tracer.start_as_current_span("produce_order_to_kafka_avro") as span:
        span.set_attribute("kafka.topic", ORDERS_TOPIC)
        span.set_attribute("order.user", order.user)
        span.set_attribute("order.id", order_id)

        try:
            key_bytes = key_serializer(
                str(order_id),
                SerializationContext(ORDERS_TOPIC, MessageField.KEY),
            )
            value_bytes = avro_value_serializer(
                order_event,
                SerializationContext(ORDERS_TOPIC, MessageField.VALUE),
            )

            producer.produce(
                topic=ORDERS_TOPIC,
                key=key_bytes,
                value=value_bytes,
                on_delivery=delivery_report,
            )
            producer.poll(0)
        except BufferError as e:
            span.record_exception(e)
            raise HTTPException(status_code=500, detail=f"Kafka buffer error: {e}")
        except SchemaRegistryError as e:
            span.record_exception(e)
            error_msg = f"Schema Registry error: {type(e).__name__}: {str(e)}"
            print(f"[api-avro] ERROR: {error_msg}")
            raise HTTPException(status_code=503, detail=error_msg)
        except Exception as e:
            span.record_exception(e)
            error_type = type(e).__name__
            error_str = str(e)
            error_module = type(e).__module__
            
            # Check if it's a connection-related error (from urllib3/requests/schema registry)
            is_connection_error = (
                error_type == "ConnectionError" or
                (RequestsConnectionError != type(None) and isinstance(e, RequestsConnectionError)) or
                "urllib3" in error_module or
                "requests" in error_module or
                "connection" in error_str.lower() or
                "Connection refused" in error_str or
                "Failed to establish" in error_str or
                "Max retries exceeded" in error_str or
                "Remote end closed" in error_str or
                "Empty reply" in error_str
            )
            
            if is_connection_error:
                error_msg = f"Connection error with Schema Registry at {SCHEMA_REGISTRY_URL}. Please ensure Schema Registry is running. Error: {error_type}: {error_str}"
                print(f"[api-avro] ERROR: {error_msg}")
                raise HTTPException(status_code=503, detail=error_msg)
            else:
                error_msg = f"Error producing order to Kafka: {error_type}: {error_str}"
                print(f"[api-avro] ERROR: {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)

    print(f"[api-avro] Queued Avro order event: {order_event}")

    return {
        "message": "Order accepted for processing (Avro)",
        "order": order_event,
    }

@app.get("/stats-avro/users/{user}")
async def get_user_stats_avro(user: str):
    # Return latest known order count for this user,
    # for the Avro-based pipeline (stats from food.orders.by_user_avro).
    with tracer.start_as_current_span("get_user_stats_avro") as span:
        span.set_attribute("stats.user", user)

        with user_counts_lock:
            count = user_counts.get(user)

        if count is None:
            span.set_attribute("stats.count", 0)
            span.set_attribute("stats.note", "No orders processed yet (Avro)")

            return {
                "user": user,
                "order_count": 0,
                "note": "No Avro orders processed yet",
            }

        span.set_attribute("stats.count", count)
        return {"user": user, "order_count": count}

# Background consumer to keep user_counts up to date (Avro pipeline)

def _stats_consumer_loop_avro():
    # Runs in a separate thread.
    # Subscribes to `food.orders.by_user_avro`, and updates user_counts.
    # Adds spans per message.
    from opentelemetry import trace
    local_tracer = trace.get_tracer("app.stats-consumer.avro")

    consumer_conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": "fastapi-stats-reader-avro",
        "auto.offset.reset": "earliest",
    }
    consumer = Consumer(consumer_conf)
    consumer.subscribe([STATS_TOPIC])

    print("[stats-consumer-avro] Started, subscribed to", STATS_TOPIC)

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"[stats-consumer-avro] Error: {msg.error()}")
                continue

            with local_tracer.start_as_current_span("process_stats_message_avro") as span:
                span.set_attribute("kafka.topic", STATS_TOPIC)
                span.set_attribute("kafka.partition", msg.partition())
                span.set_attribute("kafka.offset", msg.offset())

                user_key = msg.key().decode("utf-8") if msg.key() else None
                value_str = msg.value().decode("utf-8") if msg.value() else "0"

                try:
                    new_count = int(value_str)
                except ValueError as e:
                    span.record_exception(e)
                    print(f"[stats-consumer-avro] Could not parse count: {value_str!r}")
                    continue

                if user_key:
                    span.set_attribute("stats.user", user_key)
                    span.set_attribute("stats.count", new_count)

                    with user_counts_lock:
                        user_counts[user_key] = new_count

                    print(
                        f"[stats-consumer-avro] Updated count: user={user_key} "
                        f"count={new_count} (offset={msg.offset()})"
                    )
    finally:
        consumer.close()
        print("[stats-consumer-avro] Closed.")

@app.on_event("startup")
def start_background_stats_consumer_avro():
    # On FastAPI startup, verify Schema Registry is accessible
    try:
        schema_registry_client.get_subjects()
        print(f"[api-avro] Schema Registry connected at {SCHEMA_REGISTRY_URL}")
    except Exception as e:
        print(f"[api-avro] WARNING: Schema Registry not accessible at {SCHEMA_REGISTRY_URL}: {e}")
        print(f"[api-avro] WARNING: Avro serialization will fail until Schema Registry is started")
        print(f"[api-avro] WARNING: Start services with: docker compose up -d schema-registry")
    
    # Launch the Avro stats consumer in a daemon thread.
    t = threading.Thread(target=_stats_consumer_loop_avro, daemon=True)
    t.start()
    print("[api-avro] Background stats consumer thread started")