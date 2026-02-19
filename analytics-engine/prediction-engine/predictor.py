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
INPUT_TOPIC = 'trade-events'
OUTPUT_TOPIC = 'ai-predictions'

class HybridAIEngine:
    def __init__(self):
        self.data_buffer = []
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.min_training_size = 60
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
        
        if len(X) < 10: return "WAIT"

        unique_classes = y.unique()
        if len(unique_classes) <= 1:
            return "HOLD" 

        model = XGBClassifier(n_estimators=10, max_depth=3, eval_metric='mlogloss')
        model.fit(X, y)
        
        last_data = df[features].iloc[-1:].values
        prediction = model.predict(last_data)[0]
        
        signals = {0: "SELL", 1: "HOLD", 2: "BUY"}
        return signals.get(prediction, "HOLD")

    def train_predict_lstm(self, df):
        data = df['price'].values.reshape(-1, 1)
        scaled_data = self.scaler.fit_transform(data)
        
        X_train, y_train = [], []
        look_back = 10 
        
        if len(scaled_data) <= look_back: return float(df['price'].iloc[-1])

        for i in range(look_back, len(scaled_data)):
            X_train.append(scaled_data[i-look_back:i, 0])
            y_train.append(scaled_data[i, 0])
            
        X_train, y_train = np.array(X_train), np.array(y_train)
        X_train = np.reshape(X_train, (X_train.shape[0], X_train.shape[1], 1))
        
        model = Sequential()
        model.add(LSTM(units=50, return_sequences=False, input_shape=(X_train.shape[1], 1)))
        model.add(Dropout(0.2))
        model.add(Dense(units=1))
        model.compile(optimizer='adam', loss='mean_squared_error')
        
        model.fit(X_train, y_train, epochs=1, batch_size=1, verbose=0)
        
        last_sequence = scaled_data[-look_back:].reshape(1, look_back, 1)
        predicted_scaled = model.predict(last_sequence, verbose=0)
        predicted_price = self.scaler.inverse_transform(predicted_scaled)
        
        return float(predicted_price[0][0])

    def run(self):
        print("AI Prediction Engine Started... Waiting for Kafka messages.", flush=True)
        consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )

        for message in consumer:
            trade = message.value
            self.data_buffer.append(trade)
            
            if len(self.data_buffer) > 500:
                self.data_buffer.pop(0)

            if len(self.data_buffer) > self.min_training_size:
                df = pd.DataFrame(self.data_buffer)
                df['price'] = pd.to_numeric(df['p'])
                df['quantity'] = pd.to_numeric(df['q'])
                
                df = self.calculate_technical_features(df)
                
                xgb_signal = self.train_predict_xgboost(df.copy())
                lstm_price = self.train_predict_lstm(df.copy())
                
                result = {
                    'timestamp': trade['t'],
                    'current_price': float(trade['p']),
                    'lstm_predicted_price': lstm_price,
                    'xgb_signal': xgb_signal,
                    'rsi': float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 0
                }
                
                self.producer.send(OUTPUT_TOPIC, result)
                print(f"AI Output: LSTM Price={lstm_price:.2f} | XGB Signal={xgb_signal}", flush=True)

if __name__ == "__main__":
    engine = HybridAIEngine()
    engine.run()
