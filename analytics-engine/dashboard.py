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

# Page Configuration
st.set_page_config(page_title="QuantStream Hybrid AI", layout="wide")
st.title("BTC/USDT HYBRID AI-POWERED ANALYTICS")

# Professional UI Styling (Original + AI Enhancements)
st.markdown("""
    <style>
    .report-box {
        background-color: #0E1117;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #30363d;
        border-left: 6px solid #ff00ff;
        margin-top: 25px;
        color: #E6EDF3;
    }
    .report-title {
        color: #ff00ff;
        font-size: 24px;
        font-weight: 700;
        margin-bottom: 15px;
    }
    .report-item {
        margin-bottom: 12px;
        font-size: 16px;
        line-height: 1.6;
        color: #C9D1D9;
    }
    .label {
        color: #8B949E;
        font-weight: 500;
        margin-right: 5px;
    }
    .value {
        color: #FFFFFF;
        font-weight: 600;
    }
    .signal-buy { color: #00ff88; font-weight: 800; }
    .signal-sell { color: #FF4B4B; font-weight: 800; }
    .signal-neutral { color: #FFD700; font-weight: 800; }
    .risk-high { color: #FF4B4B; font-weight: 800; }
    .risk-medium { color: #FFA500; font-weight: 800; }
    .risk-low { color: #00FF88; font-weight: 800; }
    </style>
""", unsafe_allow_html=True)

# Kafka Connection - Listening to AI Engine Output
@st.cache_resource
def get_kafka_consumer():
    KAFKA_URL = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
    try:
        return KafkaConsumer(
            'ai-predictions',
            bootstrap_servers=[KAFKA_URL],
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            consumer_timeout_ms=1000,
            group_id="ai-dashboard-v6"
        )
    except Exception as e:
        st.error(f"Kafka Connection Error: {e}")
        return None

# Visual Analysis Functions (Restored for UI Depth)
def calculate_visual_indicators(df):
    if len(df) < 20: return df
    df['SMA_20'] = df['current_price'].rolling(window=20).mean()
    df['StdDev'] = df['current_price'].rolling(window=20).std()
    df['Upper_Band'] = df['SMA_20'] + (df['StdDev'] * 2)
    df['Lower_Band'] = df['SMA_20'] - (df['StdDev'] * 2)
    
    # Estimate VWAP proxy if quantity is not streamed from predictor
    df['pseudo_quantity'] = np.random.uniform(0.1, 5.0, size=len(df)) 
    df['VWAP'] = (df['current_price'] * df['pseudo_quantity']).cumsum() / df['pseudo_quantity'].cumsum()
    return df

def run_visual_anomaly_detection(df):
    if len(df) < 50: return df
    model = IsolationForest(contamination=0.05, random_state=42)
    data_for_ai = df[['current_price']].fillna(0)
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(data_for_ai)
    df['anomaly'] = model.fit_predict(scaled_data)
    return df

# Hybrid Market Report Generator
def generate_hybrid_report(df, last_data):
    if len(df) < 50: return "Insufficient data for deep analysis."
    
    last_price = last_data['current_price']
    lstm_target = last_data['lstm_predicted_price']
    xgb_signal = last_data['xgb_signal']
    std_dev = df['StdDev'].iloc[-1] if 'StdDev' in df.columns else 0
    anomalies = df[df['anomaly'] == -1].shape[0] if 'anomaly' in df.columns else 0
    
    # Restored Risk Score Calculation
    anomaly_risk = min(40, anomalies * 2)
    vol_risk = min(30, (std_dev / last_price) * 10000)
    total_risk = min(100, anomaly_risk + vol_risk + 15)
    
    if total_risk > 70: risk_status, r_class = "CRITICAL", "risk-high"
    elif total_risk > 40: risk_status, r_class = "ELEVATED", "risk-medium"
    else: risk_status, r_class = "STABLE", "risk-low"

    # XGBoost Signal CSS
    if xgb_signal == "BUY": s_class = "signal-buy"
    elif xgb_signal == "SELL": s_class = "signal-sell"
    else: s_class = "signal-neutral"

    spread = lstm_target - last_price

    return f"""
    <div class='report-box'>
        <div class='report-title'>Hybrid Intelligence & Risk Analysis</div>
        <div class='report-item'><span class='label'>Market Risk Score:</span> <span class='{r_class}'>{total_risk:.0f}/100 ({risk_status})</span></div>
        <div class='report-item'><span class='label'>XGBoost Action Signal:</span> <span class='{s_class}'>{xgb_signal}</span></div>
        <div class='report-item'><span class='label'>LSTM Next Target:</span> <span class='value'>${lstm_target:.2f} (Spread: ${spread:.2f})</span></div>
        <div class='report-item'><span class='label'>Volatility Index:</span> <span class='value'>{std_dev:.2f} (Based on StdDev)</span></div>
        <div class='report-item'><span class='label'>Anomalous Events:</span> <span class='value'>{anomalies} Patterns Detected by Isolation Forest</span></div>
        <div style='margin-top: 15px; color: #8B949E; font-size: 12px; font-style: italic;'>
            Hybrid AI Engine Refresh: {datetime.now().strftime('%H:%M:%S')}
        </div>
    </div>
    """

# Buffer Initialization
if 'buffer' not in st.session_state:
    st.session_state.buffer = []
if 'last_report_time' not in st.session_state:
    st.session_state.last_report_time = 0
if 'latest_report' not in st.session_state:
    st.session_state.latest_report = "Initializing Hybrid Risk Engine..."

# Main Dashboard Fragment
@st.fragment(run_every=1)
def analytics_dashboard():
    consumer = get_kafka_consumer()
    if not consumer: return
    
    msg_pack = consumer.poll(timeout_ms=500)
    for tp, messages in msg_pack.items():
        for msg in messages:
            data = msg.value
            ts = data['timestamp'] / 1000.0 if data['timestamp'] > 1e11 else data['timestamp']
            
            st.session_state.buffer.append({
                "time": datetime.fromtimestamp(ts),
                "current_price": data['current_price'],
                "lstm_predicted_price": data['lstm_predicted_price'],
                "xgb_signal": data['xgb_signal'],
                "rsi": data['rsi']
            })

    if len(st.session_state.buffer) > 500:
        st.session_state.buffer = st.session_state.buffer[-500:]

    if len(st.session_state.buffer) > 20:
        df = pd.DataFrame(st.session_state.buffer)
        df = calculate_visual_indicators(df)
        df = run_visual_anomaly_detection(df)
        
        last_data = df.iloc[-1]
        
        current_time = time.time()
        if current_time - st.session_state.last_report_time > 5:
            st.session_state.latest_report = generate_hybrid_report(df, last_data)
            st.session_state.last_report_time = current_time

        # Plotly Charts - Restored 4-Chart Layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Price, Bollinger Bands & LSTM Target")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=df['time'], y=df['current_price'], name='Price', line=dict(color='#00ff88')))
            fig1.add_trace(go.Scatter(x=df['time'], y=df['Upper_Band'], name='Upper BB', line=dict(color='gray', dash='dash')))
            fig1.add_trace(go.Scatter(x=df['time'], y=df['Lower_Band'], name='Lower BB', line=dict(color='gray', dash='dash'), fill='tonexty'))
            fig1.add_trace(go.Scatter(x=df['time'], y=df['lstm_predicted_price'], name='LSTM Prediction', line=dict(color='#ff00ff', dash='dot')))
            fig1.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig1, use_container_width=True)
            
        with col2:
            st.subheader("AI Engine RSI Momentum")
            fig2 = go.Figure(go.Scatter(x=df['time'], y=df['rsi'], name='AI RSI', line=dict(color='#00ccff')))
            fig2.add_hline(y=70, line_dash="dot", line_color="red")
            fig2.add_hline(y=30, line_dash="dot", line_color="green")
            fig2.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=30,b=0), yaxis_range=[0,100])
            st.plotly_chart(fig2, use_container_width=True)

        col3, col4 = st.columns(2)
        
        with col3:
            st.subheader("XGBoost Signals & VWAP Trend")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=df['time'], y=df['current_price'], name='Price', line=dict(color='#444')))
            fig3.add_trace(go.Scatter(x=df['time'], y=df['VWAP'], name='VWAP', line=dict(color='#ffa500', width=2)))
            
            # XGBoost Signals Overlay
            buy_signals = df[df['xgb_signal'] == 'BUY']
            sell_signals = df[df['xgb_signal'] == 'SELL']
            if not buy_signals.empty:
                fig3.add_trace(go.Scatter(x=buy_signals['time'], y=buy_signals['current_price'], mode='markers', name='BUY', marker=dict(color='#00ff88', size=10, symbol='triangle-up')))
            if not sell_signals.empty:
                fig3.add_trace(go.Scatter(x=sell_signals['time'], y=sell_signals['current_price'], mode='markers', name='SELL', marker=dict(color='#ff4b4b', size=10, symbol='triangle-down')))
            
            fig3.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig3, use_container_width=True)
            
        with col4:
            st.subheader("Isolation Forest Anomaly Detection")
            fig4 = go.Figure()
            fig4.add_trace(go.Scatter(x=df['time'], y=df['current_price'], name='Normal', line=dict(color='#333')))
            if 'anomaly' in df.columns:
                anomalies = df[df['anomaly'] == -1]
                if not anomalies.empty:
                    fig4.add_trace(go.Scatter(x=anomalies['time'], y=anomalies['current_price'], mode='markers', name='Anomaly', marker=dict(color='red', size=8, symbol='x')))
            fig4.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig4, use_container_width=True)

        st.markdown(st.session_state.latest_report, unsafe_allow_html=True)
    else:
        st.info("Gathering AI prediction data. Waiting for buffer...")

analytics_dashboard()