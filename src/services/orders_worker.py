import os, json, signal, sys, time
from confluent_kafka import Consumer, KafkaError
from opentelemetry import trace
from opentelemetry.trace import SpanKind, NonRecordingSpan, set_span_in_context
from src.otel import setup_tracing

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
ORDERS_TOPIC = os.getenv("TOPIC", "demo.orders")
GROUP_ID = os.getenv("GROUP_ID", "orders-worker")

tracer = setup_tracing("orders-worker")

def main():
    conf = {
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": GROUP_ID,
        "enable.auto.commit": False,   # control commits for at-least-once
        "auto.offset.reset": "earliest"
    }
    consumer = Consumer(conf)
    consumer.subscribe([ORDERS_TOPIC])

    print(f"[worker] Subscribed to {ORDERS_TOPIC} (group={GROUP_ID}, bootstrap={KAFKA_BOOTSTRAP})")

    running = True
    def _stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"[worker] Error: {msg.error()}", file=sys.stderr)
                continue

            headers = dict(msg.headers() or [])
            ctx = _extract_ctx(headers.get("traceparent".encode("utf-8")))
            with tracer.start_as_current_span(
                "kafka.consume",
                context=ctx,
                kind=SpanKind.CONSUMER,
                attributes={
                    "messaging.system": "kafka",
                    "messaging.destination": ORDERS_TOPIC,
                    "messaging.kafka.partition": msg.partition(),
                    "messaging.kafka.offset": msg.offset(),
                }
            ) as span:
                try:
                    order = json.loads(msg.value().decode("utf-8"))
                    _process_order(order)   # pretend business logic
                    consumer.commit(msg)    # commit after processing
                except Exception as e:
                    span.record_exception(e)
                    print(f"[worker] FAILED: {e}", file=sys.stderr)
    finally:
        consumer.close()
        print("[worker] closed")

def _extract_ctx(traceparent_bytes):
    if not traceparent_bytes:
        return None
    try:
        tp = traceparent_bytes.decode("utf-8")
        _, trace_id_hex, span_id_hex, flags_hex = tp.split("-")
        trace_id = int(trace_id_hex, 16)
        span_id = int(span_id_hex, 16)
        flags = 1 if flags_hex == "01" else 0
        span_ctx = trace.SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=True,
            trace_flags=trace.TraceFlags(flags),
            trace_state=trace.TraceState()
        )
        parent = NonRecordingSpan(span_ctx)
        return set_span_in_context(parent)
    except Exception:
        return None

def _process_order(order: dict):
    # Simulate work with its own span
    with tracer.start_as_current_span("process.order") as span:
        span.set_attribute("app.order_id", order["order_id"])
        span.set_attribute("app.user", order["user"])
        time.sleep(0.05)  # emulate IO/db
        print(f"[worker] processed order_id={order['order_id']} user={order['user']} item={order['item']} qty={order['quantity']}")

if __name__ == "__main__":
    main()