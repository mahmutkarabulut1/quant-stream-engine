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
