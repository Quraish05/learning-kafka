import os
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

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