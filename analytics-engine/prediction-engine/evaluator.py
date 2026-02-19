import os
import json
import pandas as pd
import numpy as np
from kafka import KafkaConsumer
from datetime import datetime
from collections import deque

# Kafka Configuration
KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
INPUT_TOPIC = 'ai-predictions'

class ModelEvaluator:
    def __init__(self):
        self.history = []
        self.last_prediction = None
        self.total_samples = 0
        self.correct_directions = 0
        self.lstm_errors = []
        
        # Buffer for calculating rolling accuracy (last 1000 trades)
        self.rolling_window = deque(maxlen=1000)

    def calculate_metrics(self):
        if self.total_samples == 0:
            return 0.0, 0.0

        # Directional Accuracy (XGBoost)
        dir_accuracy = (self.correct_directions / self.total_samples) * 100
        
        # LSTM Error (Mean Absolute Percentage Error)
        avg_lstm_error = np.mean(self.lstm_errors) if self.lstm_errors else 0.0
        
        return dir_accuracy, avg_lstm_error

    def process_message(self, message):
        current_data = message.value
        current_price = current_data['current_price']
        timestamp = current_data['timestamp']
        
        # If we have a prediction from the PREVIOUS step, validate it now
        if self.last_prediction is not None:
            prev_price = self.last_prediction['current_price']
            predicted_lstm_price = self.last_prediction['lstm_predicted_price']
            predicted_signal = self.last_prediction['xgb_signal']
            
            # 1. Evaluate XGBoost (Directional Accuracy)
            actual_movement = "HOLD"
            if current_price > prev_price:
                actual_movement = "BUY"
            elif current_price < prev_price:
                actual_movement = "SELL"
            
            is_correct_direction = (predicted_signal == actual_movement)
            
            # 2. Evaluate LSTM (Price Accuracy)
            # Calculate absolute percentage error
            error_margin = abs(current_price - predicted_lstm_price)
            error_percentage = (error_margin / current_price) * 100
            
            # Update Stats
            self.total_samples += 1
            if is_correct_direction:
                self.correct_directions += 1
            
            self.lstm_errors.append(error_percentage)
            
            # Log for CSV
            log_entry = {
                'timestamp': timestamp,
                'prev_price': prev_price,
                'actual_price': current_price,
                'lstm_predicted': predicted_lstm_price,
                'xgb_signal': predicted_signal,
                'actual_movement': actual_movement,
                'direction_correct': is_correct_direction,
                'lstm_error_pct': error_percentage
            }
            self.history.append(log_entry)
            
            # Periodic Console Report (Every 10 samples)
            if self.total_samples % 10 == 0:
                acc, mape = self.calculate_metrics()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Sample: {self.total_samples} | "
                      f"XGBoost Accuracy: {acc:.2f}% | "
                      f"LSTM Error Margin: {mape:.4f}%", flush=True)

                # Auto-save report every 50 samples
                if self.total_samples % 50 == 0:
                    self.save_report()

        # Store current prediction for NEXT iteration validation
        self.last_prediction = current_data

    def save_report(self):
        df = pd.DataFrame(self.history)
        filename = "model_performance_report.csv"
        df.to_csv(filename, index=False)
        print(f"--> Report saved to {filename}", flush=True)

    def run(self):
        print("Model Evaluator Started... Listening to Kafka topic: " + INPUT_TOPIC, flush=True)
        consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )

        for msg in consumer:
            self.process_message(msg)

if __name__ == "__main__":
    evaluator = ModelEvaluator()
    evaluator.run()
