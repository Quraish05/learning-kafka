#!/usr/bin/env python3
"""Produce orders from orders.jsonl to Kafka topic"""
import json
import os
from kafka import KafkaProducer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("TOPIC", "food.orders")
ORDERS_FILE = os.getenv("ORDERS_FILE", "data/orders.jsonl")

producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP,
    acks="all",
    value_serializer=lambda v: v.encode("utf-8"),  # Send as JSON string
    key_serializer=lambda k: k.encode("utf-8") if k else None,
)

print(f"Producing messages from {ORDERS_FILE} to topic '{TOPIC}' on {BOOTSTRAP}")

with open(ORDERS_FILE, "r") as f:
    for line_num, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        
        # Send the JSON line as-is (it's already a JSON string)
        future = producer.send(TOPIC, value=line, key=None)
        metadata = future.get(timeout=10)
        print(f" -> sent line {line_num + 1} to partition={metadata.partition}, offset={metadata.offset}")

producer.flush()
producer.close()
print("Done.")

