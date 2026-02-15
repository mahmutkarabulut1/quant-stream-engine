import os
import json
import numpy as np
from kafka import KafkaConsumer
from datetime import datetime
from collections import deque
from scipy import stats

# Configuration with Kubernetes Support
KAFKA_URL = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
TOPIC_NAME = 'trade-events'
WINDOW_SIZE = 100

class QuantPatternAnalyzer:
    def __init__(self):
        self.prices = deque(maxlen=WINDOW_SIZE)
        self.volumes = deque(maxlen=WINDOW_SIZE)

    def add_data(self, price, volume):
        self.prices.append(price)
        self.volumes.append(volume)

    def detect_patterns(self):
        if len(self.prices) < WINDOW_SIZE:
            return "DATA_COLLECTION_MODE"

        price_arr = np.array(self.prices)
        
        # Volatility Analysis using Z-Score: Z = (x - mu) / sigma
        z_scores = stats.zscore(price_arr)
        current_z = z_scores[-1]

        # Trend Analysis using Linear Regression Slope
        x_axis = np.arange(len(price_arr))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x_axis, price_arr)

        pattern = "STABLE"
        if current_z > 2.0 and slope > 0.01:
            pattern = "BULLISH_BREAKOUT"
        elif current_z < -2.0 and slope < -0.01:
            pattern = "BEARISH_BREAKOUT"
        elif abs(slope) < 0.001:
            pattern = "CONSOLIDATION"
            
        return {
            "pattern": pattern,
            "slope": slope,
            "z_score": current_z,
            "confidence": r_value**2
        }

def start_engine():
    print(f"Connecting to Kafka at: {KAFKA_URL}")
    
    analyzer = QuantPatternAnalyzer()
    
    try:
        consumer = KafkaConsumer(
            TOPIC_NAME,
            bootstrap_servers=[KAFKA_URL],
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )

        for message in consumer:
            data = message.value
            price = float(data['p'])
            volume = float(data['q'])
            
            analyzer.add_data(price, volume)
            results = analyzer.detect_patterns()

            if isinstance(results, dict):
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] PRICE: {price:.2f} | PATTERN: {results['pattern']} | SLOPE: {results['slope']:.4f} | CONF: {results['confidence']:.2f}")
            else:
                print(f"Status: {results} - Progress: {len(analyzer.prices)}/{WINDOW_SIZE}")

    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    start_engine()
