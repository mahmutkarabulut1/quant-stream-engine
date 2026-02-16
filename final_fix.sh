#!/bin/bash
set -e

echo "🛑 Sistem tamamen durduruluyor..."
kubectl delete deployment dashboard-engine --ignore-not-found
kubectl delete service dashboard-service --ignore-not-found
pkill -f "kubectl port-forward" || true

echo "🧹 Minikube Docker ortamına bağlanılıyor..."
eval $(minikube docker-env)

echo "📝 DOSYALAR SIFIRDAN YAZILIYOR (GARANTİLİ YÖNTEM)..."

# 1. REQUIREMENTS.TXT (Eksik olan buydu!)
cat << 'EOF_REQ' > analytics-engine/requirements.txt
kafka-python==2.0.2
pandas==2.2.0
streamlit==1.37.0
plotly==5.18.0
scikit-learn==1.4.0
aiohttp==3.9.3
EOF_REQ

# 2. DOCKERFILE (Sıralama önemli)
cat << 'EOF_DOCKER' > analytics-engine/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY analyzer.py .
COPY dashboard.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
EXPOSE 8501
CMD ["/bin/bash", "entrypoint.sh"]
EOF_DOCKER

# 3. ANALYZER.PY (Producer - Logları açık)
cat << 'EOF_PY' > analytics-engine/analyzer.py
import os
import json
import asyncio
import aiohttp
from kafka import KafkaProducer
import sys

KAFKA_URL = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
TOPIC_NAME = 'trade-events'

def get_producer():
    try:
        return KafkaProducer(
            bootstrap_servers=[KAFKA_URL],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    except Exception as e:
        print(f"❌ Kafka Bağlantı Hatası: {e}", flush=True)
        return None

async def binance_trade_stream():
    uri = "wss://stream.binance.com:9443/ws/btcusdt@trade"
    producer = get_producer()
    
    if not producer:
        print("❌ Producer başlatılamadı!", flush=True)
        return

    print(f"🚀 Binance'e bağlanılıyor: {uri}", flush=True)
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(uri) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        trade_data = json.loads(msg.data)
                        payload = {'t': trade_data['T'], 'p': trade_data['p'], 'q': trade_data['q']}
                        producer.send(TOPIC_NAME, payload)
                        print(f"✅ Veri: {payload['p']}", flush=True)
                    except Exception as e:
                        print(f"❌ Veri Hatası: {e}", flush=True)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print("❌ WebSocket Hatası!", flush=True)
                    break

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        try:
            loop.run_until_complete(binance_trade_stream())
        except Exception as e:
            print(f"⚠️ Bağlantı koptu: {e}", flush=True)
            asyncio.sleep(5)
EOF_PY

# 4. ENTRYPOINT.SH
cat << 'EOF_SH' > analytics-engine/entrypoint.sh
#!/bin/bash
set -e

echo "🔌 Sistem Başlatılıyor..."

# Kafka Bekleme
python3 -u -c "import socket, time; 
host, port = 'kafka-service', 9092; 
print(f'Waiting for Kafka at {host}:{port}...'); 
for _ in range(30):
    try:
        socket.create_connection((host, port), timeout=5); 
        print('✅ Kafka Ready!'); 
        break
    except: 
        time.sleep(2)"

# Producer Başlat
echo "🚀 Veri Motoru Başlatılıyor..."
python3 -u analyzer.py &

# Dashboard Başlat
echo "📊 Dashboard Başlatılıyor..."
exec streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0
EOF_SH
chmod +x analytics-engine/entrypoint.sh

# 5. KUBERNETES YAML
cat << 'EOF_K8S' > k8s/apps.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dashboard-engine
spec:
  replicas: 1
  selector:
    matchLabels:
      app: dashboard-engine
  template:
    metadata:
      labels:
        app: dashboard-engine
    spec:
      containers:
      - name: dashboard-engine
        image: mahmut/analytics-engine:v1
        imagePullPolicy: Never
        ports:
        - containerPort: 8501
        env:
        - name: KAFKA_BOOTSTRAP_SERVERS
          value: "kafka-service:9092"
---
apiVersion: v1
kind: Service
metadata:
  name: dashboard-service
spec:
  selector:
    app: dashboard-engine
  ports:
    - protocol: TCP
      port: 8501
      targetPort: 8501
  type: ClusterIP
EOF_K8S

echo "🏗️ İmaj YENİDEN inşa ediliyor (NO-CACHE)..."
docker build --no-cache -t mahmut/analytics-engine:v1 ./analytics-engine

echo "🚀 Kubernetes'e Deploy ediliyor..."
kubectl apply -f k8s/apps.yaml

echo "⏳ Pod bekleniyor..."
kubectl wait --for=condition=ready pod -l app=dashboard-engine --timeout=120s

echo "✅ TAMAMLANDI! Loglar açılıyor..."
