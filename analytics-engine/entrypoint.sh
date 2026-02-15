#!/bin/bash
set -e
echo "Starting Dashboard..."
python3 -c "import socket, time; 
host, port = 'kafka-service', 9092; 
print(f'Waiting for Kafka at {host}:{port}...'); 
for _ in range(30):
    try:
        socket.create_connection((host, port), timeout=5); 
        print('Kafka Ready!'); 
        break
    except: 
        time.sleep(2)"
exec streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0
