"""
Kafka Consumer for tracking orders.
This module subscribes to the 'orders' topic and prints received messages.
"""
# pylint: disable=all
import json
from confluent_kafka import Consumer

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-tracker',
    'auto.offset.reset': 'earliest'
})

consumer.subscribe(['orders'])

print("Consumer is running & subscribed to orders topic")

try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"Error: {msg.error()}")
            continue

        value = msg.value().decode('utf-8')
        order = json.loads(value)

        print(
            f"Message received: {order['item']} {order['quantity']} from {order['user']}")

except KeyboardInterrupt:
    print("Consumer is stopping")

finally:
    consumer.close()
