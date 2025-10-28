import os, json, time
from kafka import KafkaConsumer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("TOPIC", "food.orders")
GROUP = os.getenv("GROUP_ID", "kitchen-cg")
NAME  = os.getenv("CONSUMER_NAME", "kitchen-A")

# Similar to the group consumer, but includes small "processing delay"
# so you can visualize throughput and partition distribution in logs.
consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=BOOTSTRAP.split(","),
    group_id=GROUP,
    enable_auto_commit=True,
    auto_offset_reset="earliest",  # start from earliest so you can "cook" from the beginning
    value_deserializer=lambda b: json.loads(b.decode("utf-8")),
)

print(f"[{NAME}] Kitchen worker up. Group={GROUP}")
for msg in consumer:
    order = msg.value

    # Simulate different kitchens taking slightly different time:
    if order["restaurant"] in ("Tandoori Tales","Masala Magic"):
        time.sleep(0.002)  # slower items
    else:
        time.sleep(0.001)

    # Every ~3000 offsets per partition, print a status line
    if msg.offset % 3000 == 0:
        print(f"[{NAME}] cooked seq={order['seq']} from p{msg.partition} off={msg.offset}")