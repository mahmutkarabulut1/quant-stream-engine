import os
import json
import pandas as pd
from kafka import KafkaConsumer, KafkaProducer
from datetime import datetime

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
INPUT_TOPIC = 'trade-events'
OUTPUT_TOPIC = 'candle-events'

class CandleAggregator:
    def __init__(self, interval='5Min'):
        self.interval = interval
        self.buffer = []
        self.producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.current_interval_start = None

    def run(self):
        consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            auto_offset_reset='earliest',
            group_id='quantstream-aggregator-v1',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )

        print(f"Aggregator Service Started: Generating {self.interval} candles...", flush=True)

        for message in consumer:
            trade = message.value

            trade_time = pd.to_datetime(trade['t'], unit='ms')

            if self.current_interval_start is None:
                self.current_interval_start = trade_time.floor(self.interval)
            
            self.buffer.append({
                'timestamp': pd.to_datetime(trade['t'], unit='ms'),
                'price': float(trade['p']),
                'quantity': float(trade['q'])
            })

            next_interval_start = self.current_interval_start + pd.Timedelta(self.interval)

            if trade_time >= next_interval_start:
                df = pd.DataFrame(self.buffer).set_index('timestamp')
                df = df.sort_index() 
                
                last_ts = df.index.max().floor(self.interval)
                
                # BUG FIXED: Using boolean indexing instead of label slicing
                complete_trades = df[df.index < last_ts]

                if not complete_trades.empty:
                    ohlc = complete_trades['price'].resample(self.interval).ohlc()
                    volume = complete_trades['quantity'].resample(self.interval).sum()
                    
                    for ts, row in ohlc.iterrows():
                        candle = {
                            'timestamp': int(ts.timestamp() * 1000),
                            'open': row['open'],
                            'high': row['high'],
                            'low': row['low'],
                            'close': row['close'],
                            'volume': volume.loc[ts]
                        }
                        
                        self.producer.send(OUTPUT_TOPIC, candle)
                        print(f"Candle Created: {ts} | Close: {candle['close']} | Vol: {candle['volume']}", flush=True)

                    self.buffer = [t for t in self.buffer if t['timestamp'] >= last_ts]
                self.current_interval_start = trade_time.floor(self.interval)


if __name__ == "__main__":
    aggregator = CandleAggregator(interval='5Min')
    aggregator.run()
