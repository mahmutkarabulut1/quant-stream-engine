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

# --- PROFESYONEL RENK PALETİ TANIMLARI ---
COLOR_PRICE = '#00E5FF'     # Soğuk Siyan Mavi (Ana Fiyat)
COLOR_LSTM = '#D500F9'      # Derin Mor (Yapay Zeka Hedefi)
COLOR_BUY = '#00C853'       # Zümrüt Yeşili (Alım Sinyali)
COLOR_SELL = '#D50000'      # Kızıl Kırmızı (Satım Sinyali)
COLOR_HOLD = '#FFAB00'      # Kehribar Sarısı (Bekle)
COLOR_VWAP = '#FFD700'      # Altın (Hacim Ağırlıklı Ortalama)
COLOR_BB = '#546E7A'        # Mavi-Gri (Bollinger Bantları)
COLOR_RSI = '#2979FF'       # Profesyonel Mavi (Momentum)
COLOR_ANOMALY = '#FF3D00'   # Parlak Turuncu-Kırmızı (Anormallik)
COLOR_BG_SUBTLE = '#37474F' # Koyu Arka Plan Çizgileri

st.set_page_config(page_title="QuantStream Pro Terminal", layout="wide")
st.title("QuantStream | Real-Time Market Operations")

# CSS Styling - Dark Finance Theme
st.markdown(f"""
    <style>
    .report-box {{ background-color: #121212; padding: 25px; border-radius: 8px; border: 1px solid #333; border-left: 4px solid {COLOR_RSI}; margin-top: 25px; color: #E0E0E0; }}
    .report-title {{ color: {COLOR_RSI}; font-size: 22px; font-weight: 600; margin-bottom: 15px; letter-spacing: 1px; }}
    .report-item {{ margin-bottom: 10px; font-size: 15px; color: #B0BEC5; font-family: 'Roboto Mono', monospace; }}
    .label {{ color: #78909C; font-weight: 500; margin-right: 8px; }}
    .value {{ color: #FFFFFF; font-weight: 600; }}
    .signal-buy {{ color: {COLOR_BUY}; font-weight: 800; }}
    .signal-sell {{ color: {COLOR_SELL}; font-weight: 800; }}
    .signal-neutral {{ color: {COLOR_HOLD}; font-weight: 800; }}
    .risk-high {{ color: {COLOR_SELL}; font-weight: 800; }}
    .risk-medium {{ color: {COLOR_HOLD}; font-weight: 800; }}
    .risk-low {{ color: {COLOR_BUY}; font-weight: 800; }}
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_kafka_consumer():
    KAFKA_URL = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-service:9092')
    try:
        return KafkaConsumer(
            'ai-predictions',
            bootstrap_servers=[KAFKA_URL],
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            consumer_timeout_ms=500
        )
    except: return None

def calculate_visual_indicators(df):
    window = 5 if len(df) < 20 else 20
    df['SMA'] = df['current_price'].rolling(window=window, min_periods=1).mean()
    df['StdDev'] = df['current_price'].rolling(window=window, min_periods=1).std().fillna(0)
    df['Upper_Band'] = df['SMA'] + (df['StdDev'] * 2)
    df['Lower_Band'] = df['SMA'] - (df['StdDev'] * 2)
    df['pseudo_quantity'] = np.random.uniform(0.1, 5.0, size=len(df)) 
    df['VWAP'] = (df['current_price'] * df['pseudo_quantity']).cumsum() / df['pseudo_quantity'].cumsum()
    return df

def run_visual_anomaly_detection(df):
    if len(df) < 10: return df
    model = IsolationForest(contamination=0.05, random_state=42)
    data_for_ai = df[['current_price']].fillna(0)
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(data_for_ai)
    df['anomaly'] = model.fit_predict(scaled_data)
    return df

def generate_hybrid_report(df, last_data):
    if len(df) < 5: return "Waiting for more AI predictions to build deep analysis..."
    
    last_price = last_data['current_price']
    lstm_target = last_data['lstm_predicted_price']
    xgb_signal = last_data['xgb_signal']
    std_dev = df['StdDev'].iloc[-1] if 'StdDev' in df.columns else 0
    anomalies = df[df['anomaly'] == -1].shape[0] if 'anomaly' in df.columns else 0
    
    anomaly_risk = min(40, anomalies * 2)
    vol_risk = min(30, (std_dev / last_price) * 10000)
    total_risk = min(100, anomaly_risk + vol_risk + 15)
    
    if total_risk > 70: risk_status, r_class = "CRITICAL", "risk-high"
    elif total_risk > 40: risk_status, r_class = "ELEVATED", "risk-medium"
    else: risk_status, r_class = "STABLE", "risk-low"

    if xgb_signal == "BUY": s_class = "signal-buy"
    elif xgb_signal == "SELL": s_class = "signal-sell"
    else: s_class = "signal-neutral"

    spread = lstm_target - last_price

    return f"""
    <div class='report-box'>
        <div class='report-title'>QUANTSTREAM AI RISK ASSESSMENT</div>
        <div class='report-item'><span class='label'>Market Risk Score:</span> <span class='{r_class}'>{total_risk:.0f}/100 ({risk_status})</span></div>
        <div class='report-item'><span class='label'>XGBoost Action Signal:</span> <span class='{s_class}'>{xgb_signal}</span></div>
        <div class='report-item'><span class='label'>LSTM Next Target:</span> <span class='value'>${lstm_target:.2f} (Spread: ${spread:.2f})</span></div>
        <div class='report-item'><span class='label'>Volatility Index:</span> <span class='value'>{std_dev:.2f} (Based on StdDev)</span></div>
        <div class='report-item'><span class='label'>Anomalous Events:</span> <span class='value'>{anomalies} Patterns Detected</span></div>
        <div style='margin-top: 15px; color: #546E7A; font-size: 11px; font-family: monospace;'>
            SYSTEM REFRESH: {datetime.now().strftime('%H:%M:%S UTC')}
        </div>
    </div>
    """

if 'buffer' not in st.session_state:
    st.session_state.buffer = []

def process_messages():
    consumer = get_kafka_consumer()
    if not consumer: return
    
    msg_pack = consumer.poll(timeout_ms=500)
    for tp, messages in msg_pack.items():
        for msg in messages:
            data = msg.value
            # ZAMAN AKIŞI DÜZELTMESİ (Real-time arrival)
            st.session_state.buffer.append({
                "time": datetime.now(), 
                "current_price": data['current_price'],
                "lstm_predicted_price": data['lstm_predicted_price'],
                "xgb_signal": data['xgb_signal'],
                "rsi": data.get('rsi', 50)
            })
    
    if len(st.session_state.buffer) > 300:
        st.session_state.buffer = st.session_state.buffer[-300:]

def update_plotly_layout(fig, height=300, y_range=None):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        margin=dict(l=10,r=10,t=30,b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Roboto Mono, monospace", size=10, color="#B0BEC5"),
        xaxis=dict(showgrid=True, gridwidth=1, gridcolor='#263238'),
        yaxis=dict(showgrid=True, gridwidth=1, gridcolor='#263238', range=y_range)
    )

@st.fragment(run_every=1)
def draw_dashboard():
    process_messages()
    
    if len(st.session_state.buffer) > 5:
        df = pd.DataFrame(st.session_state.buffer)
        df = calculate_visual_indicators(df)
        df = run_visual_anomaly_detection(df)
        
        last_data = df.iloc[-1]
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Price Action, BB & LSTM Target")
            fig1 = go.Figure()
            # Bollinger Bands (Arka Plan)
            if 'Upper_Band' in df.columns:
                fig1.add_trace(go.Scatter(x=df['time'], y=df['Upper_Band'], name='Upper BB', line=dict(color=COLOR_BB, width=1, dash='dash')))
                fig1.add_trace(go.Scatter(x=df['time'], y=df['Lower_Band'], name='Lower BB', line=dict(color=COLOR_BB, width=1, dash='dash'), fill='tonexty', fillcolor='rgba(84, 110, 122, 0.1)'))
            # LSTM Target
            fig1.add_trace(go.Scatter(x=df['time'], y=df['lstm_predicted_price'], name='LSTM Prediction', line=dict(color=COLOR_LSTM, width=2, dash='dot')))
            # Ana Fiyat (En Üstte)
            fig1.add_trace(go.Scatter(x=df['time'], y=df['current_price'], name='BTC Price', line=dict(color=COLOR_PRICE, width=2)))
            update_plotly_layout(fig1)
            st.plotly_chart(fig1, use_container_width=True)
            
        with col2:
            st.subheader("AI Momentum (RSI)")
            fig2 = go.Figure(go.Scatter(x=df['time'], y=df['rsi'], name='RSI', line=dict(color=COLOR_RSI, width=2)))
            fig2.add_hline(y=70, line_dash="dash", line_color=COLOR_SELL, opacity=0.5, annotation_text="Overbought", annotation_position="bottom right")
            fig2.add_hline(y=30, line_dash="dash", line_color=COLOR_BUY, opacity=0.5, annotation_text="Oversold", annotation_position="bottom right")
            update_plotly_layout(fig2, y_range=[0,100])
            st.plotly_chart(fig2, use_container_width=True)

        col3, col4 = st.columns(2)
        
        with col3:
            st.subheader("XGBoost Signals & VWAP Trend")
            fig3 = go.Figure()
            # Fiyat ve VWAP
            fig3.add_trace(go.Scatter(x=df['time'], y=df['current_price'], name='Price', line=dict(color=COLOR_BG_SUBTLE, width=1)))
            if 'VWAP' in df.columns:
                fig3.add_trace(go.Scatter(x=df['time'], y=df['VWAP'], name='VWAP', line=dict(color=COLOR_VWAP, width=2)))
            
            # Sinyaller
            buy_signals = df[df['xgb_signal'] == 'BUY']
            sell_signals = df[df['xgb_signal'] == 'SELL']
            if not buy_signals.empty:
                fig3.add_trace(go.Scatter(x=buy_signals['time'], y=buy_signals['current_price'], mode='markers', name='BUY Signal', marker=dict(color=COLOR_BUY, size=12, symbol='triangle-up', line=dict(width=1, color='black'))))
            if not sell_signals.empty:
                fig3.add_trace(go.Scatter(x=sell_signals['time'], y=sell_signals['current_price'], mode='markers', name='SELL Signal', marker=dict(color=COLOR_SELL, size=12, symbol='triangle-down', line=dict(width=1, color='black'))))
            
            update_plotly_layout(fig3)
            st.plotly_chart(fig3, use_container_width=True)
            
        with col4:
            st.subheader("Isolation Forest Anomalies")
            fig4 = go.Figure()
            fig4.add_trace(go.Scatter(x=df['time'], y=df['current_price'], name='Normal Flow', line=dict(color=COLOR_BG_SUBTLE, width=1.5)))
            if 'anomaly' in df.columns:
                anomalies = df[df['anomaly'] == -1]
                if not anomalies.empty:
                    fig4.add_trace(go.Scatter(x=anomalies['time'], y=anomalies['current_price'], mode='markers', name='Anomaly Detected', marker=dict(color=COLOR_ANOMALY, size=10, symbol='x-thin', line=dict(width=2))))
            update_plotly_layout(fig4)
            st.plotly_chart(fig4, use_container_width=True)

        report_html = generate_hybrid_report(df, last_data)
        st.markdown(report_html, unsafe_allow_html=True)
    else:
        st.info("Initializing Professional AI Terminal... Gathering real-time market data.")

draw_dashboard()
