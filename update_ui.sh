#!/bin/bash
set -e

# Update dashboard.py with English-only code and no emojis
cat << 'EOF_PY' > analytics-engine/dashboard.py
import os
import time
import json
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from kafka import KafkaConsumer
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# --- Page Config ---
st.set_page_config(page_title="QuantStream AI", layout="wide")
st.title("BTC/USDT AI-POWERED ANALYTICS")

# --- Custom CSS for Report UI ---
st.markdown("""
    <style>
    .report-box {
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #00ff88;
        margin-top: 20px;
    }
    .report-title {
        color: #00ff88;
        font-size: 20px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Kafka Consumer ---
@st.cache_resource
def get_kafka_consumer():
    KAFKA_URL = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
    try:
        return KafkaConsumer(
            'trade-events',
            bootstrap_servers=[KAFKA_URL],
            auto_offset_reset='earliest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            consumer_timeout_ms=1000,
            group_id="ai-dashboard-v2"
        )
    except Exception as e:
        st.error(f"Kafka Connection Error: {e}")
        return None

# --- Indicator Calculations ---
def calculate_indicators(df):
    if len(df) < 20: return df
    
    # Bollinger Bands
    df['SMA_20'] = df['price'].rolling(window=20).mean()
    df['StdDev'] = df['price'].rolling(window=20).std()
    df['Upper_Band'] = df['SMA_20'] + (df['StdDev'] * 2)
    df['Lower_Band'] = df['SMA_20'] - (df['StdDev'] * 2)
    
    # RSI
    delta = df['price'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # VWAP
    df['VWAP'] = (df['price'] * df['quantity']).cumsum() / df['quantity'].cumsum()
    
    return df

def run_anomaly_detection(df):
    if len(df) < 50: return df
    model = IsolationForest(contamination=0.05, random_state=42)
    data_for_ai = df[['price', 'quantity']].fillna(0)
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(data_for_ai)
    df['anomaly'] = model.fit_predict(scaled_data)
    return df

# --- Market Analysis Engine ---
def generate_market_report(df):
    if len(df) < 50: return "Insufficient data for market analysis."
    
    last_price = df['price'].iloc[-1]
    first_price = df['price'].iloc[0]
    price_change = ((last_price - first_price) / first_price) * 100
    
    rsi = df['RSI'].iloc[-1]
    volatility = df['StdDev'].iloc[-1]
    anomalies = df[df['anomaly'] == -1].shape[0] if 'anomaly' in df.columns else 0
    
    trend = "SIDEWAYS"
    if price_change > 0.05: trend = "BULLISH"
    elif price_change < -0.05: trend = "BEARISH"
    
    rsi_comment = "Neutral momentum."
    if rsi > 70: rsi_comment = "Market is OVERBOUGHT. Potential pullback expected."
    elif rsi < 30: rsi_comment = "Market is OVERSOLD. Potential rebound expected."
    
    vol_comment = "Market volatility is stable."
    if volatility > df['price'].mean() * 0.001:
        vol_comment = "High volatility detected. Exercise caution."
        
    report = f"""
    <div class='report-box'>
        <div class='report-title'>Market Intelligence Report (5-Min Summary)</div>
        <ul>
            <li><b>Trend Analysis:</b> The market trend is <b>{trend}</b> with a {price_change:.3f}% price change.</li>
            <li><b>Momentum (RSI):</b> RSI is at {rsi:.1f}. {rsi_comment}</li>
            <li><b>Volatility and Risk:</b> {vol_comment} (StdDev: {volatility:.2f}).</li>
            <li><b>AI Anomaly Scan:</b> Detected <b>{anomalies}</b> anomalous trade patterns in current window.</li>
            <li><b>VWAP Signal:</b> Price is {"ABOVE" if last_price > df['VWAP'].iloc[-1] else "BELOW"} the volume-weighted average price.</li>
        </ul>
        <small><i>Report Generated at: {datetime.now().strftime('%H:%M:%S')}</i></small>
    </div>
    """
    return report

# --- State Management ---
if 'buffer' not in st.session_state:
    st.session_state.buffer = []
if 'last_report_time' not in st.session_state:
    st.session_state.last_report_time = 0
if 'latest_report' not in st.session_state:
    st.session_state.latest_report = "Waiting for data cycle to complete (5 minutes)..."

# --- Real-Time Dashboard Fragment ---
@st.fragment(run_every=1)
def analytics_dashboard():
    consumer = get_kafka_consumer()
    if not consumer: return

    msg_pack = consumer.poll(timeout_ms=500)
    for tp, messages in msg_pack.items():
        for msg in messages:
            trade = msg.value
            st.session_state.buffer.append({
                "time": datetime.now(),
                "price": float(trade.get('p', 0)),
                "quantity": float(trade.get('q', 0))
            })

    if len(st.session_state.buffer) > 500:
        st.session_state.buffer = st.session_state.buffer[-500:]

    if len(st.session_state.buffer) > 20:
        df = pd.DataFrame(st.session_state.buffer)
        df = calculate_indicators(df)
        df = run_anomaly_detection(df)
        
        # 5-Minute Report Update Trigger
        current_time = time.time()
        if current_time - st.session_state.last_report_time > 300:
            st.session_state.latest_report = generate_market_report(df)
            st.session_state.last_report_time = current_time

        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Price and Bollinger Bands")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=df['time'], y=df['price'], name='Price', line=dict(color='#00ff88')))
            fig1.add_trace(go.Scatter(x=df['time'], y=df['Upper_Band'], name='Upper BB', line=dict(color='gray', dash='dash')))
            fig1.add_trace(go.Scatter(x=df['time'], y=df['Lower_Band'], name='Lower BB', line=dict(color='gray', dash='dash'), fill='tonexty'))
            fig1.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            st.subheader("RSI Momentum")
            fig2 = go.Figure(go.Scatter(x=df['time'], y=df['RSI'], name='RSI', line=dict(color='#00ccff')))
            fig2.add_hline(y=70, line_dash="dot", line_color="red")
            fig2.add_hline(y=30, line_dash="dot", line_color="green")
            fig2.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=30,b=0), yaxis_range=[0,100])
            st.plotly_chart(fig2, use_container_width=True)

        col3, col4 = st.columns(2)

        with col3:
            st.subheader("VWAP Trend")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=df['time'], y=df['price'], name='Price', line=dict(color='#444')))
            fig3.add_trace(go.Scatter(x=df['time'], y=df['VWAP'], name='VWAP', line=dict(color='#ffa500', width=2)))
            fig3.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig3, use_container_width=True)

        with col4:
            st.subheader("AI Anomaly Detection")
            fig4 = go.Figure()
            fig4.add_trace(go.Scatter(x=df['time'], y=df['price'], name='Normal', line=dict(color='#333')))
            if 'anomaly' in df.columns:
                anomalies = df[df['anomaly'] == -1]
                if not anomalies.empty:
                    fig4.add_trace(go.Scatter(x=anomalies['time'], y=anomalies['price'], mode='markers', name='Anomaly', marker=dict(color='red', size=8, symbol='x')))
            fig4.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig4, use_container_width=True)

        st.markdown(st.session_state.latest_report, unsafe_allow_html=True)
    else:
        st.info("Gathering data for initial analysis...")

analytics_dashboard()
EOF_PY

eval $(minikube docker-env)
docker build --no-cache -t mahmut/analytics-engine:v1 ./analytics-engine
kubectl delete pod -l app=dashboard-engine
kubectl wait --for=condition=ready pod -l app=dashboard-engine --timeout=120s
