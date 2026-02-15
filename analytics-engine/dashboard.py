import os
import json
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from kafka import KafkaConsumer
from datetime import datetime
from scipy import stats
import uuid

# Professional Layout Configuration
st.set_page_config(page_title="QuantStream Elite", layout="wide", initial_sidebar_state="collapsed")

# Custom Professional UI Styling
st.markdown("""
    <style>
    .main { background-color: #05070a; color: #e6edf3; }
    [data-testid="stMetricValue"] { color: #00ff88; font-family: 'Courier New', monospace; font-size: 1.8rem; }
    .stMetric { background-color: #0c0f14; border: 1px solid #232a35; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("QUANT-STREAM: BALANCED SIGNAL INTELLIGENCE")

KAFKA_URL = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
TOPIC_NAME = 'trade-events'
WINDOW_SIZE = 100 

metrics_placeholder = st.empty()
chart_placeholder = st.empty()

if 'buffer' not in st.session_state:
    st.session_state.buffer = []

def run_dashboard():
    try:
        consumer = KafkaConsumer(
            TOPIC_NAME,
            bootstrap_servers=[KAFKA_URL],
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            consumer_timeout_ms=500
        )

        while True:
            messages = consumer.poll(timeout_ms=500)
            for tp, msgs in messages.items():
                for msg in msgs:
                    trade = msg.value
                    st.session_state.buffer.append({
                        "time": datetime.fromtimestamp(int(trade['T']) / 1000),
                        "price": float(trade['p']),
                        "volume": float(trade['q'])
                    })

            if len(st.session_state.buffer) > WINDOW_SIZE:
                st.session_state.buffer = st.session_state.buffer[-WINDOW_SIZE:]

            if len(st.session_state.buffer) >= 20:
                df = pd.DataFrame(st.session_state.buffer)
                prices = df['price'].values
                
                # Calculate 10-period SMA for smoothing
                df['sma'] = df['price'].rolling(window=10).mean()
                
                z_score = (prices[-1] - np.mean(prices)) / np.std(prices) if np.std(prices) > 1e-9 else 0
                slope, intercept, r_val, _, _ = stats.linregress(np.arange(len(prices)), prices)

                with metrics_placeholder.container():
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("LAST PRICE", f"${prices[-1]:,.2f}")
                    c2.metric("TREND SLOPE", f"{slope:.6f}")
                    c3.metric("Z-SCORE", f"{z_score:.2f}")
                    c4.metric("CONFIDENCE", f"{r_val**2:.2f}")

                # Neon Visualization
                fig = go.Figure()

                # Raw Price (Subtle/Dimmed)
                fig.add_trace(go.Scatter(
                    x=df['time'], y=df['price'],
                    name="Raw Price",
                    line=dict(color='rgba(0, 255, 136, 0.2)', width=1),
                    hoverinfo='skip'
                ))

                # Smoothed Trend (Neon Green)
                fig.add_trace(go.Scatter(
                    x=df['time'], y=df['sma'],
                    name="Smoothed Trend",
                    line=dict(color='#00ff88', width=3),
                    fill='tozeroy',
                    fillcolor='rgba(0, 255, 136, 0.05)'
                ))

                # Smart Y-Axis Scaling: Standard Deviation based padding
                price_std = np.std(prices)
                padding = price_std * 2 if price_std > 0 else 1
                
                fig.update_layout(
                    template="plotly_dark",
                    height=550,
                    margin=dict(l=0, r=0, t=20, b=0),
                    yaxis=dict(
                        range=[min(prices) - padding, max(prices) + padding],
                        gridcolor='#1a1f26',
                        showgrid=True
                    ),
                    xaxis=dict(showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                chart_placeholder.plotly_chart(fig, width='stretch', key=str(uuid.uuid4()))
            else:
                chart_placeholder.info(f"CALIBRATING_SIGNAL: {len(st.session_state.buffer)}/{WINDOW_SIZE}")

    except Exception as e:
        st.error(f"SYSTEM_ENGINE_ERROR: {e}")

if __name__ == "__main__":
    run_dashboard()
