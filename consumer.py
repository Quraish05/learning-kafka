"""
Kafka Consumer for consuming orders.
This module consumes orders from the 'orders' topic.
"""
import argparse, json, os, sys
from kafka import KafkaConsumer

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", default="group-a", help="Consumer group id")
    parser.add_argument("--from-beginning", action="store_true",
                        help="Start at earliest offset")
    args = parser.parse_args()

    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
    topic = os.getenv("TOPIC", "demo.orders")

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap,
        group_id=args.group,
        enable_auto_commit=True,
        auto_offset_reset="earliest" if args.from_beginning else "latest",
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
        consumer_timeout_ms=10000,  # stop after idle
    )

    print(f"Consuming from topic '{topic}' as group '{args.group}' (bootstrap={bootstrap})")
    try:
        for record in consumer:
            print(
                f"partition={record.partition} "
                f"offset={record.offset} "
                f"key={record.key} "
                f"value={record.value}"
            )
    finally:
        # show positions per assigned partition
        print("\nCommitted offsets (approx positions) per partition:")
        for tp in consumer.assignment():
            committed = consumer.committed(tp)
            pos = consumer.position(tp)
            print(f"  {tp.topic}-{tp.partition}: committed={committed}, next_fetch={pos}")
        consumer.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
