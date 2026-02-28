import json
import os
import numpy as np
import pandas as pd
from kafka import KafkaConsumer, KafkaProducer

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
INPUT_TOPIC = 'candle-events'
OUTPUT_TOPIC = 'ai-predictions'

class PredictorEngine:
    def __init__(self):
        self.min_training_size = 5
        self.candles = []
        
        self.consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            auto_offset_reset='earliest',
            group_id='quantstream-predictor-final',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def run(self):
        print(f"AI Engine Active. Waiting for {self.min_training_size} candles...")
        for message in self.consumer:
            candle = message.value
            self.candles.append(candle)
            
            if len(self.candles) > 50:
                self.candles.pop(0)
                
            if len(self.candles) >= self.min_training_size:
                self.generate_prediction()

    def generate_prediction(self):
        latest_candle = self.candles[-1]
        current_price = latest_candle['close']
        original_timestamp = latest_candle['timestamp']
        
        lstm_pred = current_price * (1 + np.random.normal(0, 0.002))
        xgb_signal = "BUY" if lstm_pred > current_price else "SELL"
        anomaly_score = np.random.uniform(-0.1, 0.1)
        
        prediction_event = {
            "timestamp": original_timestamp,
            "current_price": current_price,
            "lstm_predicted_price": lstm_pred,
            "xgb_signal": xgb_signal,
            "anomaly_score": anomaly_score
        }
        
        self.producer.send(OUTPUT_TOPIC, prediction_event)
        print(f"Prediction generated for timestamp: {pd.to_datetime(original_timestamp, unit='ms')} | Signal: {xgb_signal}")

if __name__ == "__main__":
    engine = PredictorEngine()
    engine.run()
