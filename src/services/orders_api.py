from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from uuid import uuid4
import json
import os
from confluent_kafka import Producer
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import get_current_span
from opentelemetry import trace

from src.otel import setup_tracing

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
ORDERS_TOPIC = os.getenv("TOPIC", "demo.orders")

app = FastAPI(title="Orders API", version="1.0.0")
tracer = setup_tracing("orders-api")

# Auto-instrument FastAPI routes (HTTP spans)
FastAPIInstrumentor.instrument_app(app)


def _kafka_producer():
    conf = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
        "linger.ms": 20,
        "acks": "1",  # Wait for leader acknowledgment (faster than "all")
        "socket.timeout.ms": 6000,
        "request.timeout.ms": 5000,
    }
    return Producer(conf)

producer = _kafka_producer()


class OrderIn(BaseModel):
    user: str = Field(..., examples=["alice"])
    item: str = Field(..., examples=["pizza"])
    quantity: int = Field(..., ge=1, le=20, examples=[2])


@app.get("/healthz")
def health():
    return {"ok": True}


@app.post("/orders")
def create_order(order: OrderIn):
    order_id = str(uuid4())
    payload = {
        "order_id": order_id,
        "user": order.user,
        "item": order.item,
        "quantity": order.quantity,
    }

    # Propagate tracing context via Kafka headers
    current_span = get_current_span()
    headers = []
    if current_span:
        current_ctx = current_span.get_span_context()
        if current_ctx and current_ctx.is_valid:
            headers.append(("traceparent", _w3c_traceparent(current_ctx).encode("utf-8")))

    def delivery_cb(err, msg):
        # This callback runs on the producer's background thread
        if err:
            # You could record an event on the active span if needed
            pass

    with tracer.start_as_current_span("kafka.produce"):
        try:
            producer.produce(
                topic=ORDERS_TOPIC,
                key=order.user.encode("utf-8"),
                value=json.dumps(payload).encode("utf-8"),
                headers=headers or None,
                on_delivery=delivery_cb,
            )
            # Flush with timeout to prevent hanging
            producer.flush(timeout=5.0)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Kafka produce failed: {e}")

    return {"status": "queued", "order_id": order_id}


def _w3c_traceparent(span_ctx):
    # Minimal W3C header formatter (version-format)
    # version(00)-traceid-spanid-flags
    version = "00"
    trace_id = f"{span_ctx.trace_id:032x}"
    span_id = f"{span_ctx.span_id:016x}"
    flags = "01" if span_ctx.trace_flags.sampled else "00"
    return f"{version}-{trace_id}-{span_id}-{flags}"
