#!/bin/bash
set -e

echo "🛑 Mevcut sistem durduruluyor..."
kubectl delete deployment dashboard-engine --ignore-not-found
kubectl delete service dashboard-service --ignore-not-found
pkill -f "kubectl port-forward" || true

echo "🧹 Minikube Docker ortamına bağlanılıyor..."
eval $(minikube docker-env)

echo "🗑️ Eski bozuk imajlar temizleniyor..."
docker rmi -f mahmut/analytics-engine:v1 || true

echo "📝 Kodlar güncelleniyor (Garantili Loglama Modu)..."

# 1. ANALYZER.PY (Flush=True ile anlık loglama)
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
                        # LOGLARI BURADA ZORLA BASIYORUZ (FLUSH=TRUE)
                        print(f"✅ Veri Gönderildi: Fiyat={payload['p']}", flush=True)
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
            print(f"⚠️ Bağlantı koptu, 5sn sonra tekrar deneniyor: {e}", flush=True)
            asyncio.sleep(5)
EOF_PY

# 2. ENTRYPOINT.SH (Unbuffered Python -u)
cat << 'EOF_SH' > analytics-engine/entrypoint.sh
#!/bin/bash
set -e

echo "🔌 Sistem Başlatılıyor (vFinal)..."

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

# Producer Başlat (-u parametresi çok önemli)
echo "🚀 Veri Motoru (Producer) Başlatılıyor..."
python3 -u analyzer.py &

# Dashboard Başlat
echo "📊 Dashboard Başlatılıyor..."
exec streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0
EOF_SH
chmod +x analytics-engine/entrypoint.sh

# 3. KUBERNETES YAML (ImagePullPolicy: Never)
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

echo "🏗️ İmaj yeniden inşa ediliyor (NO-CACHE)..."
# Context zaten ayarlı ama garanti olsun
docker build --no-cache -t mahmut/analytics-engine:v1 ./analytics-engine

echo "🚀 Kubernetes'e Deploy ediliyor..."
kubectl apply -f k8s/apps.yaml

echo "⏳ Pod'un hazır olması bekleniyor (Max 60sn)..."
kubectl wait --for=condition=ready pod -l app=dashboard-engine --timeout=60s

echo "✅ SİSTEM HAZIR! Loglar kontrol ediliyor..."
