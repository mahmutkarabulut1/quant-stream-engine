import os
import json
import numpy as np
import pandas as pd
from kafka import KafkaConsumer, KafkaProducer
from sklearn.preprocessing import MinMaxScaler
from xgboost import XGBClassifier
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
import warnings

warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
INPUT_TOPIC = 'candle-events'
OUTPUT_TOPIC = 'ai-predictions'

class HybridAIEngine:
    def __init__(self):
        self.data_buffer = []
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.min_training_size = 15 
        self.producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def calculate_technical_features(self, df):
        df['SMA_10'] = df['price'].rolling(window=10).mean()
        df['RSI'] = self.calculate_rsi(df['price'])
        df['Momentum'] = df['price'].diff(4)
        df.dropna(inplace=True)
        return df

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def train_predict_xgboost(self, df):
        df['Target'] = 1 
        df.loc[df['price'].shift(-1) > df['price'], 'Target'] = 2 
        df.loc[df['price'].shift(-1) < df['price'], 'Target'] = 0 
        
        features = ['price', 'quantity', 'SMA_10', 'RSI', 'Momentum']
        X = df[features].iloc[:-1]
        y = df['Target'].iloc[:-1]
        
        if len(X) < 10 or len(y.unique()) <= 1: 
            return "HOLD"
        
        model = XGBClassifier(n_estimators=20, max_depth=3, eval_metric='mlogloss')
        model.fit(X, y)
        
        last_data = df[features].iloc[-1:].values
        prediction = model.predict(last_data)[0]
        
        return {0: "SELL", 1: "HOLD", 2: "BUY"}.get(prediction, "HOLD")

    def train_predict_lstm(self, df):
        data = df['price'].values.reshape(-1, 1)
        scaled_data = self.scaler.fit_transform(data)
        look_back = 10
        if len(scaled_data) <= look_back: 
            return float(df['price'].iloc[-1])
            
        X_train, y_train = [], []
        for i in range(look_back, len(scaled_data)):
            X_train.append(scaled_data[i-look_back:i, 0])
            y_train.append(scaled_data[i, 0])
            
        X_train, y_train = np.array(X_train), np.array(y_train)
        X_train = np.reshape(X_train, (X_train.shape[0], X_train.shape[1], 1))
        
        model = Sequential([LSTM(50, input_shape=(X_train.shape[1], 1)), Dense(1)])
        model.compile(optimizer='adam', loss='mse')
        model.fit(X_train, y_train, epochs=2, batch_size=1, verbose=0)
        
        last_seq = scaled_data[-look_back:].reshape(1, look_back, 1)
        pred = model.predict(last_seq, verbose=0)
        return float(self.scaler.inverse_transform(pred)[0][0])

    def run(self):
        print("AI Engine Active (Standard Mode - Waiting for 15 candles)...", flush=True)
        consumer = KafkaConsumer(INPUT_TOPIC, bootstrap_servers=[KAFKA_BOOTSTRAP],
                                value_deserializer=lambda x: json.loads(x.decode('utf-8')))
        for message in consumer:
            candle = message.value
            self.data_buffer.append({'t': candle['timestamp'], 'p': candle['close'], 'q': candle['volume']})
            if len(self.data_buffer) > 200: 
                self.data_buffer.pop(0)
                
            if len(self.data_buffer) >= self.min_training_size:
                df = pd.DataFrame(self.data_buffer)
                df['price'] = pd.to_numeric(df['p'])
                df['quantity'] = pd.to_numeric(df['q'])
                
                df = self.calculate_technical_features(df)
                xgb_signal = self.train_predict_xgboost(df.copy())
                lstm_price = self.train_predict_lstm(df.copy())
                
                result = {
                    'timestamp': candle['timestamp'],
                    'current_price': float(candle['close']),
                    'lstm_predicted_price': lstm_price,
                    'xgb_signal': xgb_signal,
                    'rsi': float(df['RSI'].iloc[-1])
                }
                self.producer.send(OUTPUT_TOPIC, result)
                print(f"Prediction Generated: Target={lstm_price:.2f} | Signal={xgb_signal}", flush=True)

if __name__ == "__main__":
    HybridAIEngine().run()
