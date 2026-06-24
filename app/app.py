import time
import random
import logging

from flask import Flask
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# ---- OpenTelemetry ----
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

app = Flask(__name__)

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------- PROMETHEUS METRICS ----------------
REQUEST_COUNT = Counter("app_requests_total", "Total Requests", ["endpoint"])
REQUEST_LATENCY = Histogram("app_latency_seconds", "Latency")

# ---------------- TRACING SETUP ----------------
resource = Resource(attributes={"service.name": "observability-app"})
trace.set_tracer_provider(TracerProvider(resource=resource))

tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://jaeger:4317", insecure=True)

span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

FlaskInstrumentor().instrument_app(app)

# ---------------- ROUTES ----------------

@app.route("/")
def home():
    start = time.time()

    REQUEST_COUNT.labels(endpoint="/").inc()

    logging.info("Home endpoint called")

    with tracer.start_as_current_span("home-span"):
        time.sleep(random.uniform(0.1, 0.5))

    REQUEST_LATENCY.observe(time.time() - start)

    return "Hello Observability System!"

@app.route("/error")
def error():
    logging.error("Error endpoint triggered")
    raise Exception("Simulated error!")

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
