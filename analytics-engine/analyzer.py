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
