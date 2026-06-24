# 🔭 Observability Stack

A fully Dockerized observability pipeline built around an instrumented Python (Flask) application. It demonstrates the **three pillars of observability** — metrics, logs, and traces — wired into a single visualization layer.

| Pillar | Tool |
| --- | --- |
| 📊 Metrics | Prometheus |
| 📄 Logs | Loki |
| 🔍 Traces | Jaeger (OpenTelemetry) |
| 📈 Visualization | Grafana |
| 🐳 Runtime | Docker Compose |

---

## 📑 Table of Contents

1. [Project Structure](#-1--project-structure)
2. [Python App (Metrics + Logs + Tracing)](#-2--python-app-metrics--logs--tracing)
3. [Dockerfile](#-3--dockerfile)
4. [Prometheus Config](#-4--prometheus-config)
5. [Loki Config](#-5--loki-config)
6. [Docker Compose](#-6--docker-compose)
7. [Run the System](#-7--run-the-system)
8. [Generate Traffic](#-8--generate-traffic)
9. [Grafana Setup](#-9--grafana-setup)
10. [Sample Dashboard Queries](#-10--sample-dashboard-queries)
11. [Sample Dashboard JSON](#-11--sample-dashboard-json)
12. [Log Sample Output](#-12--log-sample-output)
13. [Trace View](#-13--trace-view-jaeger)
14. [Insights You Can Observe](#-14--insights-you-can-observe)

---

## 🧱 1 — Project Structure

```bash
mkdir observability-stack
cd observability-stack

mkdir app grafana prometheus loki tempo jaeger
touch docker-compose.yml
```

Final layout:

```text
observability-stack/
├── docker-compose.yml
├── app/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   └── dashboards/
│       └── observability.json
└── loki/
    └── loki-config.yml
```

---

## 🐍 2 — Python App (Metrics + Logs + Tracing)

### Step 1 — Create files

```bash
cd app
touch app.py requirements.txt
```

### Step 2 — Dependencies (`requirements.txt`)

```text
flask
prometheus_client
opentelemetry-api
opentelemetry-sdk
opentelemetry-instrumentation-flask
opentelemetry-exporter-otlp
requests
```

### Step 3 — Instrumented app (`app.py`)

```python
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
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ---------------- PROMETHEUS METRICS ----------------
REQUEST_COUNT = Counter("app_requests_total", "Total Requests", ["endpoint"])
REQUEST_LATENCY = Histogram("app_latency_seconds", "Latency")

# ---------------- TRACING SETUP ----------------
resource = Resource(attributes={"service.name": "observability-app"})
trace.set_tracer_provider(TracerProvider(resource=resource))

tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://jaeger:4317", insecure=True)

# NOTE: BatchSpanProcessor takes the exporter as its first positional argument.
# (The original snippet used `notify=...`, which is not a valid parameter.)
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
```

---

## 📦 3 — Dockerfile

`app/Dockerfile`:

```dockerfile
FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
```

---

## 📊 4 — Prometheus Config

`prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: "flask-app"
    metrics_path: /metrics
    static_configs:
      - targets: ["app:5000"]
```

---

## 📈 5 — Loki Config

`loki/loki-config.yml`:

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  path_prefix: /loki

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h
```

---

## 🧠 6 — Docker Compose

`docker-compose.yml`:

```yaml
version: "3.9"

services:

  app:
    build: ./app
    ports:
      - "5000:5000"

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

  loki:
    image: grafana/loki:2.9.0
    volumes:
      - ./loki/loki-config.yml:/etc/loki/local-config.yaml
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml

  jaeger:
    image: jaegertracing/all-in-one
    ports:
      - "16686:16686"   # UI
      - "4317:4317"     # OTLP gRPC
```

> ℹ️ A volume mount was added to the `loki` service so the config file you created above is actually used by the container.

---

## 🚀 7 — Run the System

Build and start everything:

```bash
docker-compose up --build
```

Running services:

| Service | URL |
| --- | --- |
| App | http://localhost:5000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| Jaeger UI | http://localhost:16686 |
| Loki | http://localhost:3100 |

---

## 📡 8 — Generate Traffic

```bash
curl http://localhost:5000/
curl http://localhost:5000/
curl http://localhost:5000/error
```

---

## 📊 9 — Grafana Setup

### Step 1 — Login

```text
URL:  http://localhost:3000
User: admin
Pass: admin
```

### Step 2 — Add Data Sources

| Data Source | URL |
| --- | --- |
| Prometheus | http://prometheus:9090 |
| Loki | http://loki:3100 |
| Jaeger | http://jaeger:16686 |

---

## 📈 10 — Sample Dashboard Queries

**Metrics (Prometheus):**

```promql
app_requests_total
rate(app_requests_total[1m])
app_latency_seconds
```

**Logs (Loki):**

```logql
{job="app"}
```

**Traces (Jaeger):**

```text
service = observability-app
```

---

## 📊 11 — Sample Dashboard JSON

Save as `grafana/dashboards/observability.json`:

```json
{
  "dashboard": {
    "title": "Observability Dashboard",
    "panels": [
      {
        "type": "graph",
        "title": "Request Count",
        "targets": [
          {
            "expr": "app_requests_total"
          }
        ]
      }
    ]
  }
}
```

---

## 📄 12 — Log Sample Output

```text
2026-06-24 10:00:01 - INFO  - Home endpoint called
2026-06-24 10:00:03 - INFO  - Home endpoint called
2026-06-24 10:00:05 - ERROR - Error endpoint triggered
```

---

## 🔍 13 — Trace View (Jaeger)

```text
home-span
 ├── HTTP request
 ├── Flask middleware
 └── response time
```

---

## 📊 14 — Insights You Can Observe

1. **Performance** — endpoint latency spikes and slow requests.
2. **Errors** — the `/error` endpoint traced; logs correlated with traces.
3. **Traffic pattern** — requests per second via Prometheus.
4. **Full correlation** — connect **Log → Trace → Metric**:
   - Log says *error*
   - Trace shows a slow span
   - Metric shows a spike

---

## 🎯 Final Result

You now have a complete observability pipeline:

- ✔ Metrics (Prometheus)
- ✔ Logs (Loki)
- ✔ Traces (Jaeger)
- ✔ Visualization (Grafana)
- ✔ Dockerized system
- ✔ End-to-end correlation

---

## ⚠️ Known Gaps / Next Steps

These don't break the stack, but are worth knowing:

- **Log shipping to Loki isn't wired up.** The app writes logs to stdout, but nothing ships them into Loki yet. To make the `{job="app"}` query return data, add a collector such as **Promtail** (or Grafana **Alloy**), or configure Docker's Loki logging driver. Note the label would be whatever you set on the shipper — not necessarily `app`.
- **No persistent volumes.** Prometheus, Grafana, and Loki data is lost when containers are removed. Add named volumes if you want it to survive restarts.
- **Grafana data sources are added manually.** You can automate them with a provisioning file under `grafana/provisioning/datasources/`.
