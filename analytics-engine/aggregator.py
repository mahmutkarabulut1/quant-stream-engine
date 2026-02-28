import json
import os
import pandas as pd
from kafka import KafkaConsumer, KafkaProducer

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
INPUT_TOPIC  = 'trade-events'
OUTPUT_TOPIC = 'candle-events'

class CandleAggregator:
    def __init__(self, interval='5Min'):
        self.interval = interval
        self.current_candle_time = None
        self.prices  = []
        self.volumes = []

        self.consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            auto_offset_reset='earliest',
            group_id='quantstream-aggregator-v6',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )

        self.producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def run(self):
        print(f"Aggregator Started: Generating {self.interval} candles...", flush=True)
        for message in self.consumer:
            trade = message.value
            try:
                price        = float(trade['p'])
                quantity     = float(trade.get('q', 1.0))
                timestamp_ms = int(trade['t'])
                trade_time   = pd.to_datetime(timestamp_ms, unit='ms')
                candle_time  = trade_time.floor(self.interval)

                if self.current_candle_time is None:
                    self.current_candle_time = candle_time
                    print(f"First trade received: {trade_time} | Price: {price}", flush=True)

                if candle_time > self.current_candle_time:
                    self.emit_candle()
                    self.current_candle_time = candle_time
                    self.prices  = []
                    self.volumes = []

                self.prices.append(price)
                self.volumes.append(quantity)

            except Exception as e:
                print(f"Error processing trade: {e} | Raw: {trade}", flush=True)

    def emit_candle(self):
        if not self.prices:
            return

        total_volume = sum(self.volumes)
        pv_sum = sum(p * v for p, v in zip(self.prices, self.volumes))

        candle = {
            "timestamp":   int(self.current_candle_time.timestamp() * 1000),
            "open":        self.prices[0],
            "high":        max(self.prices),
            "low":         min(self.prices),
            "close":       self.prices[-1],
            "volume":      total_volume,
            "pv_sum":      pv_sum,
            "trade_count": len(self.prices)
        }

        self.producer.send(OUTPUT_TOPIC, candle)
        print(f"Candle | {self.current_candle_time} | Close: {candle['close']:.2f} | Vol: {total_volume:.4f} BTC | Trades: {len(self.prices)}", flush=True)

if __name__ == "__main__":
    aggregator = CandleAggregator(interval='5Min')
    aggregator.run()
