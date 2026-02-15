import os
import json
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from kafka import KafkaConsumer
from datetime import datetime
import time

st.set_page_config(page_title="QuantStream Elite", layout="wide")
st.title("📈 BTC/USDT REAL-TIME SIGNAL")

# Kafka Ayarları
KAFKA_URL = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
TOPIC_NAME = 'trade-events'

# --- Bağlantı Fonksiyonu ---
@st.cache_resource
def get_kafka_consumer():
    try:
        consumer = KafkaConsumer(
            TOPIC_NAME,
            bootstrap_servers=[KAFKA_URL],
            auto_offset_reset='earliest',
            api_version=(2, 5, 0),
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            consumer_timeout_ms=1000,
            group_id=f"dashboard-{time.time()}"
        )
        return consumer
    except Exception as e:
        st.error(f"Kafka Hatası: {e}")
        return None

# --- Veri Tamponu ---
if 'buffer' not in st.session_state:
    st.session_state.buffer = []

# --- KRİTİK DEĞİŞİKLİK: FRAGMENT KULLANIMI ---
# Bu dekoratör, bu fonksiyonun sayfanın geri kalanından bağımsız 
# olarak kendi içinde yenilenmesini sağlar. ID çakışması OLMAZ.
@st.fragment(run_every=1)
def stream_data():
    consumer = get_kafka_consumer()
    
    if consumer:
        msg_pack = consumer.poll(timeout_ms=500)
        
        for tp, messages in msg_pack.items():
            for msg in messages:
                trade = msg.value
                st.session_state.buffer.append({
                    "time": datetime.now(),
                    "price": float(trade.get('p', 0))
                })

        # Buffer Temizliği
        if len(st.session_state.buffer) > 100:
            st.session_state.buffer = st.session_state.buffer[-100:]

        # Grafik Çizimi
        if len(st.session_state.buffer) > 2:
            df = pd.DataFrame(st.session_state.buffer)
            curr_price = df['price'].iloc[-1]
            
            # Konteyner kullanarak elemanları grupluyoruz
            with st.container():
                st.metric("CURRENT PRICE", f"${curr_price:,.2f}")
                
                fig = go.Figure(go.Scatter(
                    x=df['time'], 
                    y=df['price'], 
                    line=dict(color='#00ff88', width=2),
                    mode='lines'
                ))
                
                fig.update_layout(
                    template="plotly_dark", 
                    height=450, 
                    margin=dict(l=0,r=0,t=0,b=0),
                    xaxis_title="Time", 
                    yaxis_title="Price (USDT)"
                )
                
                # Fragment içinde olduğumuz için key sorunu yaşanmaz
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Veri bekleniyor...")

# Fonksiyonu çağırıyoruz (Otomatik olarak her 1 saniyede bir kendini yenileyecek)
stream_data()
