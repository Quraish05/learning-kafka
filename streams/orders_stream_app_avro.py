
import faust
from confluent_kafka.serialization import (SerializationContext, MessageField)
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from opentelemetry import trace

tracer = trace.get_tracer("streams.orders_stream_app_avro")

BOOTSTRAP_SERVERS = "localhost:9092"
ORDERS_TOPIC = "food.orders.avro"         # Avro input
STATS_TOPIC = "food.orders.by_user_avro"  # Avro pipeline's stats topic
SCHEMA_REGISTRY_URL = "http://localhost:8081"

# Schema Registry client + Avro deserializer
schema_registry_conf = {"url": SCHEMA_REGISTRY_URL}
schema_registry_client = SchemaRegistryClient(schema_registry_conf)

avro_value_deserializer = AvroDeserializer(
    schema_registry_client=schema_registry_client,
    schema_str=None,                     # schema ID comes from payload
    from_dict=lambda d, ctx: d,         # return dict as-is
)

# Faust App (Avro pipeline)
# IMPORTANT: aiokafka 0.12.0 has API version compatibility issues with Kafka 4.0.0 cluster setup.
# When Kafka returns metadata with all brokers (9092, 9094, 9096), aiokafka tries to connect to all,
# causing connection failures (e.g., "Connection at localhost:9096 closed").
# 
# Solutions:
# 1. Use single-broker setup (docker-compose.yml) instead of cluster (docker-compose.cluster.yml)
# 2. Or stop kafka-2 and kafka-3 temporarily: docker compose -f docker-compose.cluster.yml stop kafka-2 kafka-3
# 3. Or upgrade aiokafka when a compatible version is available
#
# Topics are pre-created to avoid CreateTopics API version issues.
app = faust.App(
    "orders-stream-app-avro",
    broker=f"kafka://{BOOTSTRAP_SERVERS}",  # primary broker
)

# Input topic: bytes (Avro), we decode manually
# Faust needs a codec that passes through raw bytes
class RawBytesCodec:
    def dumps(self, obj):
        return obj if isinstance(obj, bytes) else bytes(obj)
    
    def loads(self, s):
        # Return bytes as-is, don't decode
        if isinstance(s, bytes):
            return s
        return bytes(s) if s else b''

orders_topic = app.topic(
    ORDERS_TOPIC,
    value_serializer=RawBytesCodec(),
)

# Output topic: plain int counts
by_user_topic = app.topic(
    STATS_TOPIC,
    key_type=str,
    value_type=int,
)

# Table: per-user running count
orders_per_user = app.Table(
    "orders_per_user_avro",
    default=int,
)

@app.agent(orders_topic)
async def process(orders_stream):
    # Avro stream processor:
    # Decode Avro order via Schema Registry
    # For status == PLACED: increment orders_per_user[user]
    # Emit count to STATS_TOPIC (food.orders.by_user_avro)
    # Add an OTel span per message
    async for event in orders_stream:
        with tracer.start_as_current_span("orders_stream_avro.process") as span:
            # Get raw bytes from the event
            # Faust with RawBytesCodec: event should be bytes after codec.loads()
            # But we can also access the raw message via event.message if it's a Message object
            try:
                # Try to get raw bytes - Faust may pass the decoded value or the Message object
                value_bytes = None
                
                # If event is already bytes (from codec.loads())
                if isinstance(event, bytes):
                    value_bytes = event
                # If event is a Message object, get the raw value
                elif hasattr(event, 'message') and hasattr(event.message, 'value'):
                    value_bytes = event.message.value
                # If event has a value attribute
                elif hasattr(event, 'value'):
                    val = event.value
                    if isinstance(val, bytes):
                        value_bytes = val
                    else:
                        value_bytes = bytes(val) if val else None
                # Last resort: try to convert
                else:
                    try:
                        value_bytes = bytes(event) if event else None
                    except:
                        value_bytes = None
                
                if value_bytes is None or len(value_bytes) == 0:
                    print(f"[stream-avro] Empty or None value bytes, event type: {type(event)}")
                    continue
                
                # Verify it's Schema Registry format (magic byte 0x00, then schema ID)
                if len(value_bytes) < 5:
                    print(f"[stream-avro] Message too short ({len(value_bytes)} bytes), skipping")
                    continue
                    
                # Check magic byte
                if value_bytes[0] != 0:
                    print(f"[stream-avro] WARNING: First byte is {value_bytes[0]:02x}, expected 0x00")
                    print(f"[stream-avro] First 10 bytes (hex): {value_bytes[:10].hex()}")
                    # Don't skip - maybe it's still valid, just log the warning
                
                order = avro_value_deserializer(
                    value_bytes,
                    SerializationContext(ORDERS_TOPIC, MessageField.VALUE),
                )
                print(f"[stream-avro] ✓ Deserialized: user={order.get('user')}, status={order.get('status')}, order_id={order.get('order_id')}")
            except Exception as e:
                print(f"[stream-avro] ✗ Error: {type(e).__name__}: {e}")
                if 'value_bytes' in locals() and isinstance(value_bytes, bytes) and len(value_bytes) > 0:
                    print(f"[stream-avro] First 20 bytes (hex): {value_bytes[:20].hex()}")
                print(f"[stream-avro] Event type: {type(event)}, has value: {hasattr(event, 'value')}")
                continue  # Skip this message and continue processing

            user = order.get("user", "<unknown>")
            status = order.get("status", "")
            order_id = order.get("order_id")
            total = order.get("total", 0.0)

            span.set_attribute("order.user", user)
            span.set_attribute("order.id", order_id)
            span.set_attribute("order.status", status)
            span.set_attribute("order.total", float(total))

            if status == "PLACED":
                orders_per_user[user] += 1
                count = orders_per_user[user]

                span.set_attribute("stats.count", count)

                await by_user_topic.send(
                    key=user,
                    value=count,
                )

                print(f"[stream-avro] user={user} count={count} (order_id={order_id}, total={total})")
            else:
                print(f"[stream-avro] ignoring order_id={order_id} with status={status}")