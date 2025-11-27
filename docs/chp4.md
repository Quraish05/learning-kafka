# 🔍 Chapter 4 – FastAPI Microservice with OpenTelemetry Distributed Tracing

## Goal

Build a FastAPI-based microservice that publishes orders to Kafka, with a worker service that consumes them. Implement distributed tracing using OpenTelemetry to track requests across HTTP → Kafka → Worker boundaries, enabling end-to-end observability in a microservices architecture.

## 🎯 What You'll Learn

- Set up OpenTelemetry tracing with Jaeger for visualization
- Create a FastAPI service that produces messages to Kafka
- Build a Kafka consumer worker service
- Implement W3C traceparent header propagation through Kafka headers
- Configure OpenTelemetry Collector to forward traces to Jaeger
- Observe distributed traces across service boundaries

## 🏗 1 – Infrastructure Setup

### Add Observability Services to Docker Compose

Add OpenTelemetry Collector and Jaeger to `docker-compose.yml`:

```yaml
  otel-collector:
    image: otel/opentelemetry-collector:0.113.0
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./scripts/otel-collector-config.yaml:/etc/otel-collector-config.yaml:ro
    ports:
      - "4318:4318"   # OTLP HTTP ingest
    depends_on:
      - jaeger

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686" # Jaeger UI
```

### Create OpenTelemetry Collector Configuration

Create `scripts/otel-collector-config.yaml`:

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318

exporters:
  otlp:
    endpoint: jaeger:4317
    tls:
      insecure: true

processors:
  batch: {}

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp]
```

### Update Kafka Configuration

Change Kafka advertised listeners to use service name for Docker networking:

```yaml
KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
```

This allows services in Docker to connect using the service name `kafka` instead of `localhost`.

### Start Infrastructure

```bash
docker compose up -d kafka otel-collector jaeger
```

Verify services are running:

```bash
docker compose ps
```

Access Jaeger UI at http://localhost:16686

## 📦 2 – Install OpenTelemetry Dependencies

Add to `requirements.txt`:

```txt
opentelemetry-api==1.27.0
opentelemetry-sdk==1.27.0
opentelemetry-exporter-otlp==1.27.0
opentelemetry-instrumentation-fastapi==0.48b0
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## 🔧 3 – Create OpenTelemetry Setup Module

Create `src/otel.py`:

```python
def setup_tracing(service_name: str):
  resource = Resource.create({
    "service.name": service_name,
    "service.namespace": "food-delivery",
    "deployment.environment": os.getenv("ENV", "dev"),
  })

  provider = TracerProvider(resource=resource)
  try:
    exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318/v1/traces"))
    provider.add_span_processor(BatchSpanProcessor(exporter))
  except Exception as e:
    # If tracing setup fails, continue without tracing rather than crashing
    print(f"[tracing] Warning: Failed to setup tracing exporter: {e}. Continuing without tracing.")
  
  trace.set_tracer_provider(provider)
  return trace.get_tracer(service_name)
```

### Code Explanation

**`Resource.create({...})`**: Creates a Resource object that contains metadata about your service. This metadata is attached to every span and helps identify which service created it in Jaeger. Think of it as a "name tag" for your service.

- `"service.name"`: The name of your service (e.g., "orders-api" or "orders-worker"). This appears in Jaeger's service dropdown.
- `"service.namespace"`: Groups related services together (all "food-delivery" services appear together).
- `"deployment.environment"`: Indicates the environment (dev, staging, prod) - useful for filtering traces.

**`TracerProvider(resource=resource)`**: This is the "factory" that creates tracers. A tracer is what you use to create spans. The provider needs to know about your service (via the resource) so it can attach that info to all spans.

**`OTLPSpanExporter(endpoint=...)`**: This is the "shipping box" that sends your spans to the OpenTelemetry Collector. OTLP (OpenTelemetry Protocol) is the standard format. The endpoint tells it where to send spans (the collector's HTTP endpoint).

**`BatchSpanProcessor(exporter)`**: Instead of sending each span immediately (which is slow), this batches multiple spans together and sends them in one go. This is much more efficient - imagine mailing letters one at a time vs. putting 10 in one envelope.

**`provider.add_span_processor(...)`**: Registers the batch processor with the provider. Now whenever a span is created, it goes through this processor which batches and exports it.

**`trace.set_tracer_provider(provider)`**: Makes this provider the "global" one. When you call `trace.get_tracer()` anywhere in your code, it uses this provider.

**`trace.get_tracer(service_name)`**: Returns a tracer object. You use this tracer to create spans. The service_name is used for internal identification.

**Why the try/except?**: If the collector isn't running or unreachable, we don't want the entire application to crash. Instead, we print a warning and continue - the app works, just without tracing. This is called "graceful degradation".

## 🚀 4 – Create FastAPI Orders Service

Create `src/services/orders_api.py`:

```python
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
        if err:
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
```

### Code Explanation

**`FastAPIInstrumentor.instrument_app(app)`**: This "hooks into" FastAPI and automatically creates a span for every HTTP request. When someone calls `/orders`, it automatically creates a span called something like "POST /orders" with timing information. You don't need to write any code for this - it just works!

**`get_current_span()`**: This gets the currently active span. Because FastAPI instrumentation created a span for the HTTP request, this returns that span. If there's no active span (shouldn't happen here), it returns `None`.

**`current_span.get_span_context()`**: A span context contains the trace ID and span ID - the "coordinates" that identify this specific span in the trace. We need these to link spans together.

**`current_ctx.is_valid`**: Checks if the context is valid (not corrupted or empty). We only proceed if it's valid.

**`_w3c_traceparent(current_ctx)`**: This function converts the OpenTelemetry span context into a W3C traceparent string. The W3C format is a standard way to pass trace information between services. More on this function below.

**`headers.append(("traceparent", ...))`**: Kafka message headers are key-value pairs. We're adding a header with key "traceparent" and the W3C-formatted value. The consumer will read this header to continue the trace.

**`with tracer.start_as_current_span("kafka.produce"):`**: This creates a new span specifically for the Kafka produce operation. The `with` statement ensures the span is automatically finished when the block exits (even if there's an error). This span will be a child of the HTTP request span.

**`producer.produce(...)`**: Sends the message to Kafka. The `headers` parameter includes our traceparent header. The `on_delivery` callback is called when Kafka confirms receipt (or if there's an error).

**`producer.flush(timeout=5.0)`**: Forces the producer to send any buffered messages immediately. Without this, messages might sit in a buffer. The timeout prevents hanging forever if Kafka is down.

### The `_w3c_traceparent` Function Explained

```python
def _w3c_traceparent(span_ctx):
    version = "00"
    trace_id = f"{span_ctx.trace_id:032x}"
    span_id = f"{span_ctx.span_id:016x}"
    flags = "01" if span_ctx.trace_flags.sampled else "00"
    return f"{version}-{trace_id}-{span_id}-{flags}"
```

**Purpose**: Converts OpenTelemetry's span context (which uses integers) into the W3C traceparent string format (which uses hex strings).

**`version = "00"`**: The W3C traceparent spec version. Currently always "00".

**`f"{span_ctx.trace_id:032x}"`**: 
- `span_ctx.trace_id` is a 128-bit integer (the trace ID)
- `:032x` means "format as hexadecimal, zero-padded to 32 characters"
- Example: `123456789` becomes `"00000000000000000000075bcd15"`
- This ensures it's always exactly 32 hex characters (required by W3C spec)

**`f"{span_ctx.span_id:016x}"`**: Same idea, but for span ID (64-bit integer, 16 hex characters).

**`flags = "01" if span_ctx.trace_flags.sampled else "00"`**: 
- `sampled` means "this trace should be recorded and sent to the collector"
- `"01"` = sampled, `"00"` = not sampled
- If not sampled, the consumer might skip creating spans (saves resources)

**Return value**: A string like `"00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"` that the consumer can parse.

### ⚠️ Important: Manual Header Propagation

OpenTelemetry's automatic propagators work for HTTP headers, but not for Kafka message headers. That's why we manually:
1. Extract the current span context
2. Format it as a W3C traceparent header
3. Add it to Kafka message headers
4. The consumer will extract and use this to continue the trace

## 👷 5 – Create Kafka Consumer Worker

Create `src/services/orders_worker.py`:

```python
def main():
    conf = {
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": GROUP_ID,
        "enable.auto.commit": False,   # control commits for at-least-once
        "auto.offset.reset": "earliest"
    }
    consumer = Consumer(conf)
    consumer.subscribe([ORDERS_TOPIC])

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
    with tracer.start_as_current_span("process.order") as span:
        span.set_attribute("app.order_id", order["order_id"])
        span.set_attribute("app.user", order["user"])
        time.sleep(0.05)  # emulate IO/db
        print(f"[worker] processed order_id={order['order_id']} user={order['user']} item={order['item']} qty={order['quantity']}")
```

### Code Explanation

**`enable.auto.commit: False`**: By default, Kafka auto-commits offsets periodically. We disable this so we can commit manually after successfully processing a message. This ensures "at-least-once" semantics - if the worker crashes, it will reprocess the message (better than losing it).

**`auto.offset.reset: "earliest"`**: When the consumer group starts for the first time, read from the beginning of the topic. Alternative is `"latest"` (only new messages).

**`signal.signal(signal.SIGINT, _stop)`**: Registers a handler for Ctrl+C (SIGINT). When you press Ctrl+C, it sets `running = False` and the loop exits gracefully, allowing cleanup.

**`msg = consumer.poll(1.0)`**: Waits up to 1 second for a message. Returns `None` if no message arrives. This prevents the loop from spinning endlessly when there are no messages.

**`KafkaError._PARTITION_EOF`**: "End of File" - means we've read all messages in a partition. This is normal, not an error, so we continue.

**`headers = dict(msg.headers() or [])`**: Converts Kafka headers (list of tuples) into a dictionary for easier lookup. `or []` handles the case where headers might be `None`.

**`headers.get("traceparent".encode("utf-8"))`**: Gets the traceparent header value. Headers are bytes, so we encode the key. Returns `None` if not found.

**`ctx = _extract_ctx(...)`**: Extracts the trace context from the W3C traceparent header. This context will be used to link our consumer span to the producer span. More on this function below.

**`with tracer.start_as_current_span(..., context=ctx, kind=SpanKind.CONSUMER, ...)`**: 
- Creates a new span for consuming the message
- `context=ctx`: Makes this span a child of the producer span (links them together!)
- `kind=SpanKind.CONSUMER`: Tells OpenTelemetry this is a consumer operation. Jaeger uses this to show message flow correctly.
- `attributes={...}`: Adds metadata to the span (topic, partition, offset) for debugging

**`span.record_exception(e)`**: Records the exception on the span. In Jaeger, you'll see a red error indicator and can expand to see the exception details.

**`consumer.commit(msg)`**: Manually commits the offset after successful processing. This marks the message as "processed" so it won't be reprocessed (unless the worker crashes before this line).

### The `_extract_ctx` Function Explained

```python
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
```

**Purpose**: Converts the W3C traceparent string (from Kafka header) back into an OpenTelemetry context that we can use to link spans.

**`if not traceparent_bytes: return None`**: If there's no traceparent header (maybe the producer didn't add it, or it's an old message), we can't link spans. Return `None` and create a new trace.

**`tp.split("-")`**: Splits the traceparent string like `"00-4bf92f...-00f067aa...-01"` into parts. The `_` discards the version (we don't need it).

**`int(trace_id_hex, 16)`**: Converts hex string to integer. `16` means "base 16" (hexadecimal). Example: `"4bf92f3577b34da6a3ce929d0e0e4736"` becomes a large integer.

**`trace.SpanContext(...)`**: Creates an OpenTelemetry span context object:
- `trace_id` and `span_id`: The IDs from the traceparent
- `is_remote=True`: Indicates this context came from another service (important for OpenTelemetry)
- `trace_flags`: Whether this trace is sampled
- `trace_state`: Additional metadata (empty in our case)

**`NonRecordingSpan(span_ctx)`**: Creates a "dummy" span object that represents the parent span. We don't actually record events on it - it's just used to establish the parent-child relationship.

**`set_span_in_context(parent)`**: Wraps the parent span in a context object. When we pass this context to `start_as_current_span()`, it knows this new span should be a child of the parent.

**Why all this complexity?**: We're essentially "reconstructing" the parent span from the traceparent header. The consumer span will reference this parent, creating the link: HTTP request → Kafka produce → Kafka consume → process order.

### The `_process_order` Function Explained

```python
def _process_order(order: dict):
    with tracer.start_as_current_span("process.order") as span:
        span.set_attribute("app.order_id", order["order_id"])
        span.set_attribute("app.user", order["user"])
        time.sleep(0.05)  # emulate IO/db
        print(f"[worker] processed order_id={order['order_id']} ...")
```

**Purpose**: Simulates processing an order (in real life, this might save to a database, call another service, etc.).

**`with tracer.start_as_current_span("process.order")`**: Creates a child span under the "kafka.consume" span. This shows up in Jaeger as a nested operation.

**`span.set_attribute(...)`**: Adds custom metadata to the span. In Jaeger, you can click on a span and see these attributes. Useful for filtering ("show me all orders for user alice").

**`time.sleep(0.05)`**: Simulates work (database query, API call, etc.). The span automatically records the duration.

### Key Concepts

- **Context propagation**: The traceparent header carries trace information across service boundaries (HTTP → Kafka → Worker)
- **Span kinds**: `CONSUMER` tells Jaeger this is a message consumption operation, so it displays the flow correctly
- **Manual commits**: We commit after processing to ensure messages aren't lost if the worker crashes mid-processing
- **Nested spans**: Child spans show the breakdown of work (consume message → process order)

## 🐳 6 – Add Services to Docker Compose

Add the microservices to `docker-compose.yml`:

```yaml
  orders-api:
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./:/app
    environment:
      KAFKA_BOOTSTRAP: "kafka:9092"
      TOPIC: "demo.orders"
      OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-collector:4318/v1/traces"
      ENV: "dev"
    command: bash -lc "pip install -r requirements.txt && uvicorn src.services.orders_api:app --host 0.0.0.0 --port 8080"
    ports:
      - "8080:8080"
    depends_on:
      - kafka
      - otel-collector

  orders-worker:
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./:/app
    environment:
      KAFKA_BOOTSTRAP: "kafka:9092"
      TOPIC: "demo.orders"
      GROUP_ID: "orders-worker"
      OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-collector:4318/v1/traces"
      ENV: "dev"
    command: bash -lc "pip install -r requirements.txt && python -m src.services.orders_worker"
    depends_on:
      - kafka
      - otel-collector
```

## 🚀 7 – Run the Services

### Start All Services

```bash
docker compose up -d
```

### Check Service Logs

```bash
# Check orders-api logs
docker compose logs -f orders-api

# Check orders-worker logs
docker compose logs -f orders-worker

# Check otel-collector logs
docker compose logs -f otel-collector
```

### Create a Topic (if needed)

```bash
docker exec -it kafka bash
kafka-topics.sh --create --topic demo.orders --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
```

## 🧪 8 – Test the System

### Send a Test Order

```bash
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{
    "user": "alice",
    "item": "pizza",
    "quantity": 2
  }'
```

Expected response:

```json
{
  "status": "queued",
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Verify Worker Processing

Check the worker logs:

```bash
docker compose logs orders-worker | grep processed
```

You should see:

```
[worker] processed order_id=550e8400-e29b-41d4-a716-446655440000 user=alice item=pizza qty=2
```

## 🔍 9 – View Traces in Jaeger

1. Open Jaeger UI: http://localhost:16686
2. Select service: `orders-api` or `orders-worker`
3. Click "Find Traces"
4. You should see traces showing:
   - HTTP request span (from FastAPI)
   - Kafka produce span (from orders-api)
   - Kafka consume span (from orders-worker)
   - Process order span (from orders-worker)

### Trace Structure

A complete trace should show:

```
HTTP POST /orders (orders-api)
  └── kafka.produce (orders-api)
      └── kafka.consume (orders-worker)
          └── process.order (orders-worker)
```

## 🐛 10 – Common Issues and Fixes

### Issue: Traces Not Appearing in Jaeger

**Symptoms**: No traces visible in Jaeger UI

**Solutions**:
1. Check OTel collector logs: `docker compose logs otel-collector`
2. Verify environment variable: `OTEL_EXPORTER_OTLP_ENDPOINT` is set correctly
3. Check network connectivity between services
4. Ensure Jaeger is running: `docker compose ps jaeger`

### Issue: Trace Context Not Propagated

**Symptoms**: Traces appear but are not connected (separate traces for API and worker)

**Solutions**:
1. Verify traceparent header is being added in `orders_api.py`
2. Check that headers are being extracted in `orders_worker.py`
3. Ensure `_w3c_traceparent` and `_extract_ctx` functions are correct
4. Check Kafka message headers: `kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic demo.orders --from-beginning --property print.headers=true`

### Issue: Kafka Connection Errors

**Symptoms**: `Connection refused` or `Bootstrap server` errors

**Solutions**:
1. Verify Kafka is running: `docker compose ps kafka`
2. Check `KAFKA_BOOTSTRAP` environment variable uses service name `kafka:9092` (not `localhost`)
3. Ensure services are on the same Docker network
4. Check Kafka advertised listeners configuration

## 📚 11 – Key Concepts

### Distributed Tracing

Distributed tracing tracks requests as they flow through multiple services. Each operation creates a **span**, and spans are linked together to form a **trace**.

### W3C Traceparent Header

The W3C traceparent header format:
```
version-traceid-spanid-flags
00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

- **version**: Always `00` for current spec
- **trace-id**: 32 hex characters (128 bits)
- **span-id**: 16 hex characters (64 bits)
- **flags**: 2 hex characters (sampling flag)

### Span Kinds

- **SERVER**: Incoming HTTP request (auto-created by FastAPI instrumentation)
- **CLIENT**: Outgoing HTTP request
- **PRODUCER**: Message sent to messaging system
- **CONSUMER**: Message received from messaging system
- **INTERNAL**: Internal operation

### Context Propagation

Context propagation ensures that spans created in different services are linked together. In Kafka, this is done by:
1. Producer: Encoding trace context into message headers
2. Consumer: Extracting trace context from message headers
3. Creating child spans that reference the parent context

## 🎯 End-of-Chapter Checklist

- ✅ Set up OpenTelemetry Collector and Jaeger
- ✅ Created FastAPI service with Kafka producer
- ✅ Created Kafka consumer worker service
- ✅ Implemented W3C traceparent header propagation
- ✅ Verified end-to-end traces in Jaeger UI
- ✅ Understood distributed tracing concepts

## 🔗 Next Steps

- Explore adding more services to the trace (e.g., payment service, notification service)
- Add custom attributes and events to spans for better observability
- Implement trace sampling for high-throughput scenarios
- Add metrics and logs correlation with traces

