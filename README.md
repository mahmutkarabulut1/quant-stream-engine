# QuantStream: Real-Time Financial Data Pipeline and AI Forecasting

QuantStream is a distributed, end-to-end financial data engineering project designed to ingest, process, and analyze high-frequency trade data from Binance via WebSockets. The system leverages a microservices architecture orchestrated on Kubernetes, utilizing Apache Kafka as a resilient message backbone and hybrid AI models for real-time risk assessment and price forecasting.

## System Architecture

The project is built on a modular, event-driven architecture consisting of four primary layers:

1.  **Ingestion Layer (Java / Spring Boot):** High-throughput service that maintains a persistent WebSocket connection to Binance, capturing raw trade events and producing them to Kafka topics.
2.  **Stream Processing Layer (Python / Pandas):** An optimized aggregator that transforms raw trade ticks into deterministic 5-minute OHLCV (Open, High, Low, Close, Volume) candles using an O(1) time-boundary windowing strategy.
3.  **Intelligence Layer (TensorFlow / XGBoost):** A quantitative engine that utilizes LSTM networks for price target prediction, XGBoost for signal generation, and Isolation Forest for real-time anomaly detection.
4.  **Visualization Layer (Streamlit):** A live dashboard providing real-time observability of market metrics, including VWAP, Bollinger Bands, and AI-driven risk scores.

## Key Technical Features

### Optimized Data Aggregation
The aggregator service implements a stateful windowing logic that avoids redundant DataFrame reconstructions. By monitoring time boundaries instead of buffer sizes, the system achieves constant time complexity for real-time stream processing, ensuring zero-lag during high-volatility periods.

### Hybrid AI Forecasting
- **LSTM (Long Short-Term Memory):** Predicts future price targets based on historical temporal patterns.
- **XGBoost:** Generates actionable signals (Buy/Sell/Hold) by analyzing momentum and volatility indicators.
- **Isolation Forest:** Identifies market anomalies and "fat-finger" events in real-time.

### Infrastructure and Observability
- **Kubernetes Orchestration:** All services are containerized and managed via K8s deployments with self-healing capabilities and automated rollouts.
- **Message Reliability:** Apache Kafka ensures fault tolerance and state recovery, allowing consumers to replay data from specific offsets.
- **Observability Suite:** Includes a custom bash-based monitoring utility for real-time pod health and log analysis.

## Prerequisites

- Kubernetes Cluster (Minikube / EKS / GKE)
- Helm (for Kafka/Zookeeper deployment)
- Docker
- Python 3.9+
- JDK 17+

## Deployment

1. Start the infrastructure:
   ```bash
   kubectl apply -f k8s/infrastructure/
   ```

2. Deploy the microservices:
   ```bash
   kubectl apply -f k8s/services/
   ```

3. Access the dashboard:
   ```bash
   kubectl port-forward service/dashboard-service 8501:8501
   ```

## Development Team
- **Mahmut:** AI & Data Engineer - Model architecture, stream processing optimization, and data pipeline design.
- **Bengi:** Infrastructure Engineer - Kubernetes orchestration, Kafka configuration, and backend resilience.

## License
This project is licensed under the MIT License.
