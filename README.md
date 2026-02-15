# QuantStream: Real-Time Financial Data Pipeline and Visualization Engine

QuantStream is a high-throughput, fault-tolerant distributed system designed to ingest, process, and visualize real-time cryptocurrency trade data. Built with a microservices architecture on Kubernetes, it leverages Apache Kafka for event streaming and Streamlit with fragment-based rendering for low-latency visualization.

## System Architecture

The system follows a producer-consumer pattern decoupled by a message broker, ensuring scalability and resilience against backpressure.

### 1. Data Ingestion Layer (Producer)
- **Source:** Binance WebSocket API.
- **Mechanism:** Asynchronous Python client (aiohttp) establishes a persistent connection to the btcusdt@trade stream.
- **Serialization:** Raw JSON payloads are serialized into bytes and pushed to the Kafka topic 'trade-events'.
- **Fault Tolerance:** Implements automatic reconnection logic with exponential backoff strategies for WebSocket stability.

### 2. Message Broker Layer (Kafka)
- **Topic:** trade-events
- **Configuration:** Single-node Kafka broker deployed via Bitnami Helm charts on Kubernetes.
- **Retention Policy:** Configured for high-throughput, short-retention bursts to optimize storage for real-time analysis.

### 3. Analytics and Visualization Engine (Consumer)
- **Framework:** Streamlit (Python).
- **Consumer Logic:** kafka-python library creates a consumer group (dashboard-group) to read messages.
- **Rendering Optimization:**
  - Utilizes the '@st.fragment' decorator to isolate chart component updates.
  - Prevents full-page re-renders, reducing CPU/Memory usage significantly.
  - Eliminates "DuplicateElementId" errors by managing component lifecycles independently.
- **Data Buffer:** A rolling window buffer (circular queue) retains the last N data points for plotting, ensuring O(1) memory complexity.

## Tech Stack and Key Decisions

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Orchestration** | Kubernetes (Minikube) | Provides self-healing pods, service discovery, and declarative infrastructure. |
| **Streaming** | Apache Kafka | Decouples producers/consumers, handles backpressure, and ensures exactly-once delivery semantics. |
| **Visualization** | Streamlit + Plotly | Enables rapid prototyping. Plotly provides hardware-accelerated SVG/WebGL charts. |
| **Language** | Python 3.11 | Extensive ecosystem for data engineering (pandas, numpy) and network programming. |

## Installation and Deployment

This project uses a Makefile to abstract complex Docker and Kubernetes commands into simple verbs.

### Prerequisites
- Docker
- Minikube
- kubectl

### Quick Start Workflow

1. **Initialize the Environment**
   This command cleans legacy resources, builds the Docker image (using cache for speed), applies Kubernetes manifests, and waits for pod readiness.

   make setup

2. **Access the Dashboard**
   Establishes a secure tunnel from the Kubernetes cluster to localhost.

   make tunnel

   > Access the UI at: http://localhost:8501

3. **Monitor Logs**
   View real-time ingestion and processing logs.

   make logs

4. **Clean Up**
   Remove all resources and kill background port forwarding processes.

   make clean

## Project Structure

.
├── analytics-engine/       # Microservice: Dashboard and Consumer
│   ├── Dockerfile          # Multi-stage build for Python env
│   ├── dashboard.py        # Streamlit app with Fragment architecture
│   ├── entrypoint.sh       # Smart startup script with Kafka health checks
│   └── requirements.txt    # Python dependencies
├── k8s/                    # Infrastructure as Code (IaC)
│   └── apps.yaml           # Deployment and Service definitions
├── Makefile                # Automation scripts
└── README.md               # Documentation

## Troubleshooting and Resilience Implementation

### Zombie Process Handling
The Makefile includes aggressive cleanup routines (using fuser and pkill) to terminate orphaned processes on port 8501, resolving common ADDRINUSE errors during development iterations.

### Kafka Connection Reliability
The entrypoint.sh script implements a "wait-for-it" pattern. It polls the Kafka service availability using raw sockets before starting the Streamlit application, preventing the "CrashLoopBackOff" state caused by race conditions.

### Memory Optimization
By switching from st.rerun() to @st.fragment, the application avoids the memory ballooning associated with full-script re-execution loops in Streamlit, ensuring stability over long-running sessions.

---
**Author:** Mahmut
**License:** MIT
