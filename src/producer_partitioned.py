import json, os, time, uuid, argparse, random
from kafka import KafkaProducer

# You can point to localhost:9092 / 9094 / 9096
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("TOPIC", "demo.orders")

def make_order():
    order_id = str(uuid.uuid4())[:8]
    payload = {
        "order_id": order_id,
        "user_id": random.randint(1000, 2000),
        "items": [{"sku": random.choice(["PIZZA-MARG", "PIZZA-PEP", "GARLIC-BREAD"]), "qty": 1}],
        "amount": round(random.uniform(5, 25), 2),
        "status": "CREATED"
    }
    return order_id, payload

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--acks", default="all", choices=["0","1","all"])
    args = parser.parse_args()

    print(f"args={args} acks={args.acks})")

    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        acks=args.acks,             # leader + ISR ack when "all"
        retries=10,
        linger_ms=10,
        key_serializer=lambda s: s.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    print(f"[producer_partitioned] Producing to {TOPIC} (bootstrap={BOOTSTRAP}, acks={args.acks})")
    for _ in range(args.count):
        order_id, payload = make_order()
        fut = producer.send(TOPIC, key=order_id, value=payload, headers=[("event-type", b"order-created")])
        md = fut.get(timeout=10)
        print(f"Sent order {payload['order_id']} -> partition {md.partition}, offset {md.offset}")
        time.sleep(args.delay)

    producer.flush()
    producer.close()

if __name__ == "__main__":
    main()
