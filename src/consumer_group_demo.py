"""
Group-aware consumer to visualize partition assignment & offsets.
Run multiple instances with the same --group to observe rebalancing.
"""
import argparse, json, os
from kafka import KafkaConsumer

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", default="group-a", help="Consumer group id")
    parser.add_argument("--topic", default=os.getenv("TOPIC", "demo.orders"))
    parser.add_argument("--from-beginning", action="store_true", help="Start at earliest offset")
    args = parser.parse_args()

    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

    consumer = KafkaConsumer(
        args.topic,
        bootstrap_servers=bootstrap,
        group_id=args.group,
        enable_auto_commit=True,
        auto_offset_reset="earliest" if args.from_beginning else "latest",
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
        consumer_timeout_ms=0,
    )

    print(f"[{args.group}] Consuming {args.topic} (bootstrap={bootstrap})")
    for msg in consumer:
        headers = {k: (v.decode() if v else None) for (k, v) in (msg.headers or [])}
        print(
            f"[{args.group}] p={msg.partition} off={msg.offset} key={msg.key} "
            f"value={msg.value} headers={headers}"
        )

if __name__ == "__main__":
    main()
