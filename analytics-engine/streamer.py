import os
import json
import time
import websocket # websocket-client kütüphanesi
from kafka import KafkaProducer

KAFKA_URL = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
TOPIC_NAME = 'trade-events'

def get_producer():
    for _ in range(10): # Kafka'nın hazır olmasını bekleme döngüsü
        try:
            return KafkaProducer(
                bootstrap_servers=[KAFKA_URL],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks=1
            )
        except Exception as e:
            print(f"Waiting for Kafka: {e}", flush=True)
            time.sleep(3)
    return None

def on_message(ws, message):
    try:
        trade_data = json.loads(message)
        payload = {'t': trade_data['T'], 'p': trade_data['p'], 'q': trade_data['q']}
        producer.send(TOPIC_NAME, payload)
        # Sadece 10 saniyede bir log bas (performans için)
        if int(time.time()) % 10 == 0:
            print(f"Data Streaming: {payload['p']}", flush=True)
    except Exception as e:
        print(f"Send Error: {e}", flush=True)

def on_error(ws, error):
    print(f"WebSocket Error: {error}", flush=True)

def on_close(ws, close_status_code, close_msg):
    print("### Closed ###", flush=True)

def connect():
    # ping_interval Binance ile bağlantıyı canlı tutar (Heartbeat)
    ws = websocket.WebSocketApp("wss://stream.binance.com:9443/ws/btcusdt@trade",
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    ws.run_forever(ping_interval=30, ping_timeout=10)

if __name__ == "__main__":
    producer = get_producer()
    if producer:
        while True:
            try:
                connect()
            except Exception as e:
                print(f"Reconnect due to: {e}", flush=True)
                time.sleep(5)