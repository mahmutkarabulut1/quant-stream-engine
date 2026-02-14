import json
import numpy as np
from kafka import KafkaConsumer
from datetime import datetime
from collections import deque

# Kafka Configuration
TOPIC_NAME = 'trade-events'
BOOTSTRAP_SERVERS = ['localhost:9092']

# Financial Parameters
WINDOW_SIZE = 50       # Number of data points to keep for analysis
RSI_PERIOD = 14        # Period for RSI calculation
SMA_PERIOD = 20        # Period for Simple Moving Average

class FinancialAnalyzer:
    def __init__(self):
        # Efficient queue to store the last N prices
        self.prices = deque(maxlen=WINDOW_SIZE)

    def add_price(self, price):
        self.prices.append(price)

    def calculate_sma(self):
        if len(self.prices) < SMA_PERIOD:
            return None
        # Calculate Simple Moving Average of the last N items
        return np.mean(list(self.prices)[-SMA_PERIOD:])

    def calculate_rsi(self):
        if len(self.prices) < RSI_PERIOD + 1:
            return None

        prices_list = list(self.prices)[-(RSI_PERIOD+1):]
        deltas = np.diff(prices_list)
        
        gains = deltas[deltas > 0]
        losses = -deltas[deltas < 0]

        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0

        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def get_signal(self, rsi):
        if rsi is None:
            return "WAITING"
        if rsi < 30:
            return "OVERSOLD (BUY)"
        elif rsi > 70:
            return "OVERBOUGHT (SELL)"
        else:
            return "NEUTRAL"

def start_engine():
    print(">>> Starting Quantitative Analytics Engine...")
    print(">>> Connecting to Kafka...")

    try:
        consumer = KafkaConsumer(
            TOPIC_NAME,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        
        analyzer = FinancialAnalyzer()

        print(f">>> Connection successful. Analyzing real-time trade data...")
        print(">>> Collecting initial data for indicators (need 20+ trades)...")

        for message in consumer:
            trade_data = message.value
            
            # Extract Data
            current_price = float(trade_data['p'])
            timestamp = int(trade_data['T']) / 1000
            human_time = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')

            # Add to analyzer
            analyzer.add_price(current_price)

            # Calculate Indicators
            sma = analyzer.calculate_sma()
            rsi = analyzer.calculate_rsi()
            signal = analyzer.get_signal(rsi)

            # Formatting Output
            sma_str = f"{sma:.2f}" if sma else "CALCULATING..."
            rsi_str = f"{rsi:.2f}" if rsi else "CALCULATING..."
            
            # Print tabular hard data
            print(f"[{human_time}] Price: {current_price:.2f} | SMA({SMA_PERIOD}): {sma_str} | RSI({RSI_PERIOD}): {rsi_str} | Signal: {signal}")

    except Exception as e:
        print(f">>> Error: {e}")

if __name__ == "__main__":
    start_engine()
