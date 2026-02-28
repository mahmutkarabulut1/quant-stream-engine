import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import json
import os
import time
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from kafka import KafkaConsumer
from sklearn.ensemble import IsolationForest

st.set_page_config(
    page_title="QuantStream | BTC/USDT Terminal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@300;400;600;700&display=swap');
  .stApp { background: #0a0e1a; color: #e2e8f0; font-family: 'Inter', sans-serif; }
  #MainMenu, footer, header { visibility: hidden; }
  .terminal-header { background: linear-gradient(135deg, #0f1729 0%, #1a2340 100%); border: 1px solid #1e3a5f; border-radius: 8px; padding: 16px 24px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
  .terminal-title { font-family: 'JetBrains Mono', monospace; font-size: 22px; font-weight: 600; color: #00d4ff; letter-spacing: 2px; }
  .terminal-subtitle { font-size: 12px; color: #64748b; letter-spacing: 1px; margin-top: 2px; }
  .kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }
  .kpi-card { background: #0f1729; border: 1px solid #1e3a5f; border-radius: 8px; padding: 14px 16px; }
  .kpi-label { font-size: 10px; color: #64748b; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 6px; }
  .kpi-value { font-family: 'JetBrains Mono', monospace; font-size: 20px; font-weight: 600; color: #e2e8f0; }
  .kpi-change-up { color: #00e676; font-size: 12px; }
  .kpi-change-down { color: #ff5252; font-size: 12px; }
  .warmup-banner { background: linear-gradient(90deg, #1a1f35 0%, #0f1729 100%); border: 1px solid #334155; border-left: 3px solid #ffab00; border-radius: 6px; padding: 12px 18px; margin: 12px 0; font-size: 12px; color: #94a3b8; font-family: 'JetBrains Mono', monospace; }
  .warmup-banner span { color: #ffab00; font-weight: 600; }
  .status-live { color: #00e676; font-weight: 600; font-size: 12px; font-family: 'JetBrains Mono', monospace; }
  .status-waiting { color: #ffab00; font-size: 12px; font-family: 'JetBrains Mono', monospace; }
</style>
""", unsafe_allow_html=True)

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
TOPIC = 'ai-predictions'

MIN_RSI  = 14
MIN_MACD = 26
MIN_BB   = 20
MIN_VOL  = 14
MIN_ISO  = 10

DARK_BG       = '#0a0e1a'
CARD_BG       = '#0f1729'
GRID_COLOR    = '#1e3a5f'
PRICE_COLOR   = '#00d4ff'
RSI_COLOR     = '#818cf8'
MACD_COLOR    = '#34d399'
SIGNAL_COLOR  = '#f87171'
VWAP_COLOR    = '#fbbf24'
BB_COLOR      = 'rgba(99,179,237,0.12)'
BB_LINE       = 'rgba(99,179,237,0.5)'
ANOMALY_COLOR = '#ff5252'

def create_consumer():
    return KafkaConsumer(
        TOPIC,
        bootstrap_servers=[KAFKA_BOOTSTRAP],
        auto_offset_reset='earliest',
        group_id=f'quant-dashboard-{int(time.time())}',
        value_deserializer=lambda x: json.loads(x.decode('utf-8')),
        consumer_timeout_ms=1000
    )

def compute_indicators(df):
    closes = df['current_price']
    n = len(df)

    if n >= MIN_BB:
        df['sma20']    = closes.rolling(MIN_BB, min_periods=MIN_BB).mean()
        df['bb_std']   = closes.rolling(MIN_BB, min_periods=MIN_BB).std()
        df['upper_bb'] = df['sma20'] + 2 * df['bb_std']
        df['lower_bb'] = df['sma20'] - 2 * df['bb_std']
        df['bb_width'] = (df['upper_bb'] - df['lower_bb']) / df['sma20'] * 100
    else:
        df['sma20'] = df['upper_bb'] = df['lower_bb'] = df['bb_width'] = np.nan

    if n >= MIN_RSI:
        delta = closes.diff()
        gain  = delta.where(delta > 0, 0).ewm(com=MIN_RSI - 1, adjust=False).mean()
        loss  = (-delta.where(delta < 0, 0)).ewm(com=MIN_RSI - 1, adjust=False).mean()
        rs    = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
    else:
        df['rsi'] = np.nan

    if n >= MIN_MACD:
        ema12             = closes.ewm(span=12, adjust=False).mean()
        ema26             = closes.ewm(span=26, adjust=False).mean()
        df['macd']        = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist']   = df['macd'] - df['macd_signal']
    else:
        df['macd'] = df['macd_signal'] = df['macd_hist'] = np.nan

    # Session VWAP — günlük sıfırlanır
    vol_col = 'volume' if ('volume' in df.columns and df['volume'].sum() > 0) else None
    df['_date'] = df['datetime'].dt.date
    if vol_col:
        df['_pv']      = closes * df[vol_col]
        df['_cum_pv']  = df.groupby('_date')['_pv'].cumsum()
        df['_cum_vol'] = df.groupby('_date')[vol_col].cumsum()
        df['vwap']     = df['_cum_pv'] / df['_cum_vol']
    else:
        df['vwap'] = df.groupby('_date')['current_price'].expanding().mean().reset_index(level=0, drop=True)
    df.drop(columns=['_date', '_pv', '_cum_pv', '_cum_vol'], errors='ignore', inplace=True)

    if n >= MIN_ISO:
        feat = df[['current_price', 'lstm_predicted_price']].copy()
        feat['rsi_f'] = df['rsi'].fillna(50)
        df['outlier'] = IsolationForest(contamination=0.05, random_state=42, n_estimators=50).fit_predict(feat.values)
    else:
        df['outlier'] = 1

    df['returns']    = closes.pct_change()
    df['volatility'] = df['returns'].rolling(MIN_VOL, min_periods=MIN_VOL).std() * 100 if n >= MIN_VOL else np.nan

    # RSI renk sınıflandırması (grafik renklendirme için)
    df['rsi_zone'] = 'neutral'
    if n >= MIN_RSI:
        df.loc[df['rsi'] >= 70, 'rsi_zone'] = 'overbought'
        df.loc[df['rsi'] <= 30, 'rsi_zone'] = 'oversold'

    return df

def compute_net_bias(report, df):
    """7 rapor maddesinden net bias skoru üretir."""
    bullish_score = 0
    bearish_score = 0
    neutral_score = 0

    bias_map = {
        'badge-bullish': 'bullish',
        'badge-bearish': 'bearish',
        'badge-neutral': 'neutral',
        'badge-warning': 'neutral',
        'badge-danger':  'bearish',
        'badge-waiting': None,
    }

    for item in report:
        side = bias_map.get(item['cls'])
        if side == 'bullish':   bullish_score += 1
        elif side == 'bearish': bearish_score += 1
        elif side == 'neutral': neutral_score += 1

    total = bullish_score + bearish_score + neutral_score
    if total == 0:
        return None

    net = bullish_score - bearish_score

    if net >= 3:
        bias_label, bias_cls, bias_emoji = "STRONG BULLISH", "badge-bullish", "🟢"
    elif net >= 1:
        bias_label, bias_cls, bias_emoji = "MILD BULLISH", "badge-bullish", "🟡"
    elif net == 0:
        bias_label, bias_cls, bias_emoji = "MIXED SIGNALS", "badge-neutral", "⚪"
    elif net >= -2:
        bias_label, bias_cls, bias_emoji = "MILD BEARISH", "badge-bearish", "🟡"
    else:
        bias_label, bias_cls, bias_emoji = "STRONG BEARISH", "badge-bearish", "🔴"

    # Destek / direnç seviyeleri
    last = df.iloc[-1]
    support    = last['lower_bb'] if not pd.isna(last.get('lower_bb')) else None
    resistance = last['upper_bb'] if not pd.isna(last.get('upper_bb')) else None
    vwap       = last['vwap']     if not pd.isna(last.get('vwap'))     else None

    sr_text = ""
    if support and resistance:
        sr_text = f"Support: <strong>${support:,.2f}</strong> (Lower BB) &nbsp;|&nbsp; Resistance: <strong>${resistance:,.2f}</strong> (Upper BB)"
        if vwap:
            sr_text += f" &nbsp;|&nbsp; VWAP: <strong>${vwap:,.2f}</strong>"

    summary = (
        f"{bias_emoji} <strong>{bullish_score} Bullish</strong> / "
        f"<strong>{bearish_score} Bearish</strong> / "
        f"<strong>{neutral_score} Nötr</strong> &nbsp;→&nbsp; "
        f"<strong>{bias_label}</strong>"
    )

    return {
        "label":  bias_label,
        "cls":    bias_cls,
        "score":  f"{bullish_score}B / {bearish_score}S / {neutral_score}N",
        "summary": summary,
        "sr_text": sr_text,
    }

def generate_report(df):
    report = []
    last = df.iloc[-1]
    n = len(df)

   # 1. Price Trend
    if n >= 2:
        chg = (last['current_price'] - df.iloc[0]['current_price']) / df.iloc[0]['current_price'] * 100
        up  = chg > 0
        report.append({
            "badge": "BULLISH" if up else "BEARISH",
            "cls":   "badge-bullish" if up else "badge-bearish",
            "text":  f"Price moved <strong>{abs(chg):.2f}%</strong> {'upward' if up else 'downward'} over the period. Current price is <strong>${last['current_price']:,.2f}</strong>. {'Buying pressure dominates.' if up else 'Selling pressure persists.'}"
        })

    # 2. Bollinger Bands
    if n >= MIN_BB and not pd.isna(last.get('upper_bb')):
        p = last['current_price']
        bb_pos = (p - last['lower_bb']) / (last['upper_bb'] - last['lower_bb'] + 1e-9) * 100
        if p > last['upper_bb']:
            report.append({"badge": "BB OVERBOUGHT", "cls": "badge-warning", "text": f"Price broke above the <strong>Upper Bollinger Band (${last['upper_bb']:,.2f})</strong>. Overbought territory; high risk of a short-term correction."})
        elif p < last['lower_bb']:
            report.append({"badge": "BB OVERSOLD", "cls": "badge-bullish", "text": f"Price dropped below the <strong>Lower Bollinger Band (${last['lower_bb']:,.2f})</strong>. Oversold territory; high probability of mean-reversion."})
        else:
            report.append({"badge": "BB NEUTRAL", "cls": "badge-neutral", "text": f"Price is within BB (${last['lower_bb']:,.2f}–${last['upper_bb']:,.2f}). Position: <strong>{bb_pos:.0f}%</strong>. Width: <strong>{last['bb_width']:.2f}%</strong> {'— squeeze, breakout imminent!' if last['bb_width'] < 1.5 else '— normal volatility'}."})
    else:
        report.append({"badge": "AWAITING BB", "cls": "badge-waiting", "text": f"<strong>{MIN_BB} data points</strong> required for Bollinger Bands. Current: <strong>{n}</strong>. Active in <strong>{max(0,MIN_BB-n)}</strong> more points."})
    
    # 3. RSI
    if n >= MIN_RSI and not pd.isna(last.get('rsi')):
        r = last['rsi']
        if r >= 70:   
            report.append({"badge": "RSI OVERBOUGHT",  "cls": "badge-warning", "text": f"RSI is <strong>{r:.1f}</strong> — overbought. Consider reviewing stop-loss levels."})
        elif r <= 30: 
            report.append({"badge": "RSI OVERSOLD", "cls": "badge-bullish", "text": f"RSI is <strong>{r:.1f}</strong> — oversold. Potential technical rebound zone."})
        elif r > 55:  
            report.append({"badge": "RSI BULLISH",     "cls": "badge-bullish", "text": f"RSI is <strong>{r:.1f}</strong> — moderate upward momentum. Trend may continue."})
        elif r < 45:  
            report.append({"badge": "RSI BEARISH",     "cls": "badge-bearish", "text": f"RSI is <strong>{r:.1f}</strong> — moderate downward momentum. Bottom discovery may persist."})
        else:         
            report.append({"badge": "RSI NEUTRAL",        "cls": "badge-neutral", "text": f"RSI is <strong>{r:.1f}</strong> — neutral zone. Look to other indicators for confirmation."})    
    
    else:
        report.append({"badge": "AWAITING RSI", "cls": "badge-waiting", "text": f"<strong>{MIN_RSI} data points</strong> required for RSI(14). Current: <strong>{n}</strong>. Active in <strong>{max(0,MIN_RSI-n)}</strong> more points."})
    
    # 4. MACD
    if n >= MIN_MACD and not pd.isna(last.get('macd')):
        mv, sv, hv = last['macd'], last['macd_signal'], last['macd_hist']
        prev = df.iloc[-2]
        ph   = prev.get('macd_hist', hv)
        if mv > sv and (pd.isna(prev.get('macd')) or prev['macd'] <= prev.get('macd_signal', prev['macd'])):
            report.append({"badge": "BULLISH CROSSOVER", "cls": "badge-bullish", "text": f"MACD <strong>crossed above the signal line</strong>. MACD: <strong>{mv:.2f}</strong>, Signal: <strong>{sv:.2f}</strong>. Strong buy signal."})
        elif mv < sv and (pd.isna(prev.get('macd')) or prev['macd'] >= prev.get('macd_signal', prev['macd'])):
            report.append({"badge": "BEARISH CROSSOVER", "cls": "badge-bearish", "text": f"MACD <strong>crossed below the signal line</strong>. MACD: <strong>{mv:.2f}</strong>, Signal: <strong>{sv:.2f}</strong>. Selling pressure is increasing."})        
        
        else:
                expanding = abs(hv) > abs(ph)
                hdir = "expanding" if expanding else "contracting"
                
                if mv > sv:
                    if expanding:
                        badge, cls, note = "MACD BULLISH", "badge-bullish", "Positive momentum is strengthening. Upward pressure continues."
                    else:
                        badge, cls, note = "MACD WEAKENING", "badge-warning", "Positive momentum is weakening. Possible trend reversal."
                else:
                    if expanding:
                        badge, cls, note = "MACD BEARISH", "badge-bearish", "Negative momentum is strengthening. Downward pressure continues."
                    else:
                        badge, cls, note = "MACD RECOVERING", "badge-warning", "Negative momentum is weakening. Selling pressure is decreasing."
                        
                report.append({"badge": badge, "cls": cls, "text": f"MACD is in <strong>{'positive' if mv>0 else 'negative'} territory</strong> ({mv:.2f}), Signal: {sv:.2f}, histogram is {hdir}. {note}"})    
    
    else:
        report.append({"badge": "AWAITING MACD", "cls": "badge-waiting", "text": f"<strong>{MIN_MACD} data points</strong> required for MACD(12/26/9) (26-period EMA). Current: <strong>{n}</strong>. Active in <strong>{max(0,MIN_MACD-n)}</strong> more points."})
    
    # 5. VWAP
    if not pd.isna(last.get('vwap')):
        p, v = last['current_price'], last['vwap']
        d = (p - v) / v * 100
        if p > v: 
            report.append({"badge": "ABOVE VWAP",  "cls": "badge-bullish", "text": f"Price is <strong>{abs(d):.2f}% above VWAP</strong> (Session VWAP: ${v:,.2f}). Trading above institutional average cost; VWAP acting as support."})
        else:     
            report.append({"badge": "BELOW VWAP", "cls": "badge-bearish", "text": f"Price is <strong>{abs(d):.2f}% below VWAP</strong> (Session VWAP: ${v:,.2f}). Trading below institutional average cost; downward pressure persists."})
    
    # 6. Anomaly
    if n >= MIN_ISO:
        ac = (df['outlier'] == -1).sum()
        ra = df.tail(3)['outlier'].eq(-1).any()
        if ra:   
            report.append({"badge": "ANOMALY DETECTED",   "cls": "badge-danger",  "text": f"<strong>Abnormal movement detected</strong> in the last 3 data points (Isolation Forest). Total {ac} anomalies. Potential flash crash or large order spike."})
        elif ac: 
            report.append({"badge": "PAST ANOMALY", "cls": "badge-warning", "text": f"<strong>{ac} anomalies</strong> detected in the period; normal market flow in recent data points."})
        else:    
            report.append({"badge": "CLEAN SIGNAL",     "cls": "badge-bullish", "text": "No abnormal movements detected in the analysis period. Market flow is nominal."})
    else:
        report.append({"badge": "AWAITING ANOMALY DATA", "cls": "badge-waiting", "text": f"<strong>{MIN_ISO} data points</strong> required for Isolation Forest. Current: <strong>{n}</strong>."})

    # 7. Volatility
    if n >= MIN_VOL and not pd.isna(last.get('volatility')):
        vv = last['volatility']
        if vv > 0.5:   
            report.append({"badge": "HIGH VOLATILITY", "cls": "badge-warning", "text": f"14-period volatility is <strong>{vv:.3f}%</strong> — high. Consider reducing position sizing and widening stop-loss distances."})
        elif vv > 0.2: 
            report.append({"badge": "NORMAL VOLATILITY",   "cls": "badge-neutral", "text": f"14-period volatility is <strong>{vv:.3f}%</strong> — normal market conditions."})
        else:          
            report.append({"badge": "LOW VOLATILITY",  "cls": "badge-neutral", "text": f"14-period volatility is <strong>{vv:.3f}%</strong> — consolidation. Could be a precursor to a major breakout."})
    else:
        report.append({"badge": "AWAITING VOLATILITY DATA", "cls": "badge-waiting", "text": f"<strong>{MIN_VOL} data points</strong> required for Volatility. Current: <strong>{n}</strong>."})

    return report

def render_warmup_banner(n):
    inds = []
    if n < MIN_BB:   inds.append(f"BB({MIN_BB})")
    if n < MIN_RSI:  inds.append(f"RSI({MIN_RSI})")
    if n < MIN_MACD: inds.append(f"MACD({MIN_MACD})")
    if n < MIN_VOL:  inds.append(f"VOL({MIN_VOL})")
    if not inds:
        return ""
    pct = min(int(n / MIN_MACD * 100), 100)
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    return (f"<div class='warmup-banner'>PIPELINE WARMING UP — <span>{n} / {MIN_MACD}</span> data points collected "
            f"| Progress: <span>[{bar}] {pct}%</span> | Pending: <span>{', '.join(inds)}</span></div>")

def build_report_html(report_items, bias, n):
    if not report_items:
        return ""

    items_html = ""
    for item in report_items:
        items_html += f'<div class="report-item"><span class="report-badge {item["cls"]}">{item["badge"]}</span><span class="report-text">{item["text"]}</span></div>'

   # Net Bias HTML block
    bias_html = ""
    if bias:
        bias_html = f"""
        <div class="bias-container">
            <div class="bias-header">⬡ NET BIAS SYNTHESIS</div>
            <div class="bias-score-row">
                <span class="report-badge {bias['cls']}" style="min-width:180px;font-size:11px;">{bias['label']}</span>
                <span class="bias-score-text">{bias['summary']}</span>
            </div>
            {f'<div class="bias-sr">{bias["sr_text"]}</div>' if bias['sr_text'] else ''}
        </div>"""

    now = datetime.now().strftime('%H:%M:%S')
    return f"""<!DOCTYPE html><html><head>

<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@300;400;600;700&display=swap');
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0f1729;font-family:'Inter',sans-serif;padding:20px 24px;}}
.report-title{{font-family:'JetBrains Mono',monospace;font-size:13px;color:#00d4ff;letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid #1e3a5f;}}
.report-item{{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid #141e30;}}
.report-item:last-child{{border-bottom:none;}}
.report-badge{{min-width:140px;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:1px;text-align:center;font-family:'JetBrains Mono',monospace;}}
.badge-bullish{{background:rgba(0,230,118,0.15);color:#00e676;border:1px solid #00e676;}}
.badge-bearish{{background:rgba(255,82,82,0.15);color:#ff5252;border:1px solid #ff5252;}}
.badge-neutral{{background:rgba(100,116,139,0.15);color:#94a3b8;border:1px solid #475569;}}
.badge-warning{{background:rgba(255,171,0,0.15);color:#ffab00;border:1px solid #ffab00;}}
.badge-danger{{background:rgba(255,82,82,0.2);color:#ff5252;border:1px solid #ff5252;}}
.badge-waiting{{background:rgba(51,65,85,0.3);color:#475569;border:1px solid #334155;}}
.report-text{{font-size:13px;color:#94a3b8;line-height:1.6;}}
.report-text strong{{color:#e2e8f0;}}
.bias-container{{margin-top:20px;padding:16px 20px;background:rgba(0,212,255,0.04);border:1px solid #1e3a5f;border-top:2px solid #00d4ff;border-radius:6px;}}
.bias-header{{font-family:'JetBrains Mono',monospace;font-size:11px;color:#00d4ff;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;}}
.bias-score-row{{display:flex;align-items:center;gap:14px;margin-bottom:10px;}}
.bias-score-text{{font-size:13px;color:#94a3b8;}}
.bias-score-text strong{{color:#e2e8f0;}}
.bias-sr{{font-size:12px;color:#64748b;margin-top:6px;padding-top:8px;border-top:1px solid #1e3a5f;}}
.bias-sr strong{{color:#94a3b8;}}
</style></head><body>
<div class="report-title">⬡ AI FINANCIAL REPORT — {now} UTC &nbsp;|&nbsp; {n} DATA POINTS</div>
{items_html}
{bias_html}
</body></html>"""

def build_charts(df):
    n = len(df)
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=[
            "BTC/USDT — Price & Bollinger Bands",
            "MACD (12 / 26 / 9)",
            "RSI (14) — Momentum Oscillator",
            "Session VWAP & Price",
            "Volatility (14-Period σ%)",
            "Isolation Forest — Anomaly Detection",
        ],
        vertical_spacing=0.10, horizontal_spacing=0.07,
        row_heights=[0.40, 0.30, 0.30],
    )
    ax = dict(
        showgrid=True, gridwidth=1, gridcolor=GRID_COLOR,
        zeroline=False, showline=True, linecolor=GRID_COLOR,
        tickfont=dict(color='#64748b', size=10),
    )
    fig.update_layout(
        paper_bgcolor=DARK_BG, plot_bgcolor=CARD_BG,
        font=dict(color='#e2e8f0', family='Inter', size=11),
        margin=dict(l=45, r=150, t=45, b=30), showlegend=True,
        legend=dict(
            bgcolor='rgba(15,23,41,0.9)', bordercolor=GRID_COLOR, borderwidth=1,
            font=dict(size=10, color='#94a3b8'), orientation='v',
            yanchor='top', y=1.01, xanchor='right', x=1.12,
        ),
        height=880,
        hoverlabel=dict(bgcolor='#0f1729', bordercolor=GRID_COLOR, font=dict(color='#e2e8f0', size=11)),
    )
    for ann in fig.layout.annotations:
        ann.update(font=dict(color='#94a3b8', size=11))

    # ── Row 1 Col 1: Price + BB ──
    if n >= MIN_BB:
        # BB dolgu alanı
        fig.add_trace(go.Scatter(
            x=df['datetime'], y=df['upper_bb'], name='Upper BB',
            line=dict(color=BB_LINE, width=1),
            hovertemplate='Upper BB: $%{y:,.2f}<extra></extra>'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df['datetime'], y=df['lower_bb'], name='Lower BB',
            fill='tonexty', fillcolor=BB_COLOR,
            line=dict(color=BB_LINE, width=1),
            hovertemplate='Lower BB: $%{y:,.2f}<extra></extra>'
        ), row=1, col=1)
        # SMA20 orta çizgi
        fig.add_trace(go.Scatter(
            x=df['datetime'], y=df['sma20'], name='SMA 20',
            line=dict(color='rgba(148,163,184,0.4)', width=1, dash='dot'),
            hovertemplate='SMA20: $%{y:,.2f}<extra></extra>'
        ), row=1, col=1)

    # Fiyat çizgisi + alan dolgusu
    fig.add_trace(go.Scatter(
        x=df['datetime'], y=df['current_price'], name='BTC/USDT',
        line=dict(color=PRICE_COLOR, width=2),
        fillcolor='rgba(0,212,255,0.04)',
        hovertemplate='BTC: $%{y:,.2f}<extra></extra>'
    ), row=1, col=1)

    # ── Row 1 Col 2: MACD ──
    if n >= MIN_MACD:
        hc = ['rgba(52,211,153,0.8)' if (v is not None and not np.isnan(v) and v >= 0)
              else 'rgba(248,113,113,0.8)' for v in df['macd_hist']]
        fig.add_trace(go.Bar(
            x=df['datetime'], y=df['macd_hist'], name='Histogram',
            marker_color=hc, opacity=0.8,
            hovertemplate='Hist: %{y:.2f}<extra></extra>'
        ), row=1, col=2)
        fig.add_trace(go.Scatter(
            x=df['datetime'], y=df['macd'], name='MACD',
            line=dict(color=MACD_COLOR, width=2),
            hovertemplate='MACD: %{y:.2f}<extra></extra>'
        ), row=1, col=2)
        fig.add_trace(go.Scatter(
            x=df['datetime'], y=df['macd_signal'], name='Signal',
            line=dict(color=SIGNAL_COLOR, width=1.5, dash='dot'),
            hovertemplate='Signal: %{y:.2f}<extra></extra>'
        ), row=1, col=2)
        fig.add_hline(y=0, line_color='rgba(148,163,184,0.3)', line_width=1, row=1, col=2)
    else:
        fig.add_annotation(text=f"MACD için {max(0,MIN_MACD-n)} more points required",
                           xref="x2 domain", yref="y2 domain", x=0.5, y=0.5,
                           showarrow=False, font=dict(color='#475569', size=12))

    # ── Row 2 Col 1: RSI — renkli bölgeler ──
    if n >= MIN_RSI:
        # Overbought bölgesi dolgusu
        fig.add_hrect(y0=70, y1=100, fillcolor='rgba(255,82,82,0.05)',
                      line_width=0, row=2, col=1)
        # Oversold bölgesi dolgusu
        fig.add_hrect(y0=0, y1=30, fillcolor='rgba(0,230,118,0.05)',
                      line_width=0, row=2, col=1)

        # RSI çizgisi — bölgeye göre renk
        rsi_colors = []
        for val in df['rsi']:
            if pd.isna(val):       rsi_colors.append(RSI_COLOR)
            elif val >= 70:        rsi_colors.append('#ff5252')
            elif val <= 30:        rsi_colors.append('#00e676')
            else:                  rsi_colors.append(RSI_COLOR)

        fig.add_trace(go.Scatter(
            x=df['datetime'], y=df['rsi'], name='RSI (14)',
            line=dict(color=RSI_COLOR, width=2),
            fill='tozeroy', fillcolor='rgba(129,140,248,0.05)',
            hovertemplate='RSI: %{y:.1f}<extra></extra>'
        ), row=2, col=1)

        fig.add_hline(y=70, line_dash='dash', line_color='rgba(255,82,82,0.5)', line_width=1,
                      annotation_text='OB 70', annotation_font_color='#ff5252',
                      annotation_position='right', row=2, col=1)
        fig.add_hline(y=30, line_dash='dash', line_color='rgba(0,230,118,0.5)', line_width=1,
                      annotation_text='OS 30', annotation_font_color='#00e676',
                      annotation_position='right', row=2, col=1)
        fig.add_hline(y=50, line_color='rgba(148,163,184,0.2)', line_width=1, row=2, col=1)
        fig.update_yaxes(range=[0, 100], row=2, col=1)
    else:
        fig.add_annotation(text=f"For RSI {max(0,MIN_RSI-n)} more points required",
                           xref="x3 domain", yref="y3 domain", x=0.5, y=0.5,
                           showarrow=False, font=dict(color='#475569', size=12))

    # ── Row 2 Col 2: Session VWAP ──
    fig.add_trace(go.Scatter(
        x=df['datetime'], y=df['current_price'], name='Price',
        line=dict(color='rgba(71,85,105,0.8)', width=1.5),
        hovertemplate='Price: $%{y:,.2f}<extra></extra>'
    ), row=2, col=2)
    fig.add_trace(go.Scatter(
        x=df['datetime'], y=df['vwap'], name='Session VWAP',
        line=dict(color=VWAP_COLOR, width=2.5),
        hovertemplate='VWAP: $%{y:,.2f}<extra></extra>'
    ), row=2, col=2)
    # VWAP etrafında kanal
    if not df['vwap'].isna().all():
        std_price = df['current_price'].std()
        if not np.isnan(std_price):
            fig.add_trace(go.Scatter(
                x=df['datetime'], y=df['vwap'] + std_price, name='VWAP+1σ',
                line=dict(color='rgba(251,191,36,0.25)', width=1, dash='dot'),
                showlegend=False
            ), row=2, col=2)
            fig.add_trace(go.Scatter(
                x=df['datetime'], y=df['vwap'] - std_price, name='VWAP-1σ',
                line=dict(color='rgba(251,191,36,0.25)', width=1, dash='dot'),
                fill='tonexty', fillcolor='rgba(251,191,36,0.04)',
                showlegend=False
            ), row=2, col=2)

    # ── Row 3 Col 1: Volatilite ──
    if n >= MIN_VOL:
        vc = ['rgba(255,171,0,0.7)' if (v is not None and not np.isnan(v) and v > 0.5)
              else 'rgba(52,211,153,0.5)' for v in df['volatility']]
        fig.add_trace(go.Bar(
            x=df['datetime'], y=df['volatility'], name='Volatilite %',
            marker_color=vc,
            hovertemplate='Vol: %{y:.3f}%<extra></extra>'
        ), row=3, col=1)
        fig.add_hline(y=0.5, line_dash='dash', line_color='rgba(255,171,0,0.4)',
                      annotation_text='High Vol 0.5%', annotation_font_color='#ffab00',
                      annotation_position='right', row=3, col=1)
    else:
        fig.add_annotation(text=f"For volatilite {max(0,MIN_VOL-n)} more points required",
                           xref="x5 domain", yref="y5 domain", x=0.5, y=0.5,
                           showarrow=False, font=dict(color='#475569', size=12))

    # ── Row 3 Col 2: Anomali ──
    fig.add_trace(go.Scatter(
        x=df['datetime'], y=df['current_price'],
        line=dict(color='rgba(51,65,85,0.8)', width=1.5),
        showlegend=False, name='Price',
        hovertemplate='Price: $%{y:,.2f}<extra></extra>'
    ), row=3, col=2)

    if n >= MIN_ISO:
        nd = df[df['outlier'] == 1]
        ad = df[df['outlier'] == -1]
        fig.add_trace(go.Scatter(
            x=nd['datetime'], y=nd['current_price'],
            mode='markers', name='Normal',
            marker=dict(color='rgba(71,85,105,0.6)', size=4),
            hovertemplate='Normal: $%{y:,.2f}<extra></extra>'
        ), row=3, col=2)
        if not ad.empty:
            fig.add_trace(go.Scatter(
                x=ad['datetime'], y=ad['current_price'],
                mode='markers+text', name='Anomaly',
                marker=dict(color=ANOMALY_COLOR, size=12, symbol='x',
                            line=dict(width=2.5, color=ANOMALY_COLOR)),
                text=[f"${v:,.0f}" for v in ad['current_price']],
                textposition='top center',
                textfont=dict(size=9, color=ANOMALY_COLOR),
                hovertemplate='⚠ Anomali: $%{y:,.2f}<extra></extra>'
            ), row=3, col=2)
    else:
        fig.add_annotation(text=f"For anomaly {max(0,MIN_ISO-n)} more points required",
                           xref="x6 domain", yref="y6 domain", x=0.5, y=0.5,
                           showarrow=False, font=dict(color='#475569', size=12))

    fig.update_xaxes(**ax)
    fig.update_yaxes(**ax)
    return fig

def main():
    st.markdown("""
    <div class="terminal-header">
      <div>
        <div class="terminal-title">◈ QUANTSTREAM TERMINAL</div>
        <div class="terminal-subtitle">BTC/USDT · REAL-TIME MARKET ANALYTICS · POWERED BY KAFKA + AI ENGINE</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:11px;color:#334155;">BINANCE STREAM</div>
        <div style="font-size:11px;color:#334155;margin-top:2px;">ML PIPELINE ACTIVE</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    status_ph = st.empty()
    warmup_ph = st.empty()
    kpi_ph    = st.empty()
    chart_ph  = st.empty()
    report_ph = st.empty()

    if 'data_buffer' not in st.session_state:
        st.session_state.data_buffer = []

    consumer = create_consumer()

    while True:
        for message in consumer:
            data = message.value
            data['datetime'] = pd.to_datetime(data['timestamp'], unit='ms')
            st.session_state.data_buffer.append(data)

        if len(st.session_state.data_buffer) > 500:
            st.session_state.data_buffer = st.session_state.data_buffer[-500:]

        n = len(st.session_state.data_buffer)

        if n >= 2:
            df   = pd.DataFrame(st.session_state.data_buffer)
            df   = compute_indicators(df)
            last = df.iloc[-1]
            price      = last['current_price']
            prev_price = df.iloc[-2]['current_price']
            pdelta     = price - prev_price
            dpct       = (pdelta / prev_price) * 100

            dc = '#00e676' if pdelta >= 0 else '#ff5252'
            da = '▲' if pdelta >= 0 else '▼'
            status_ph.markdown(
                f"<div class='status-live'>● PIPELINE ACTIVE &nbsp;|&nbsp; LAST TICK: {last['datetime'].strftime('%H:%M:%S')} &nbsp;|&nbsp; "
                f"<span style='color:{dc}'>{da} ${abs(pdelta):.2f} ({abs(dpct):.3f}%)</span> &nbsp;|&nbsp; {n} DATA POINTS</div>",
                unsafe_allow_html=True)

            warmup_ph.markdown(render_warmup_banner(n), unsafe_allow_html=True)

            rsi_v  = last['rsi']         if not pd.isna(last.get('rsi',   np.nan)) else None
            macd_v = last['macd']        if not pd.isna(last.get('macd',  np.nan)) else None
            msig_v = last['macd_signal'] if not pd.isna(last.get('macd_signal', np.nan)) else None
            bbw_v  = last['bb_width']    if not pd.isna(last.get('bb_width', np.nan)) else None
            vol_v  = last['volatility']  if not pd.isna(last.get('volatility', np.nan)) else None
            rc = '#ff5252' if (rsi_v and rsi_v >= 70) else ('#00e676' if (rsi_v and rsi_v <= 30) else '#e2e8f0')
            mc = '#00e676' if (macd_v and msig_v and macd_v > msig_v) else '#ff5252'

            kpi_ph.markdown(f"""
                <div class="kpi-grid">
                <div class="kpi-card"><div class="kpi-label">BTC / USDT</div><div class="kpi-value" style="color:#00d4ff;">${price:,.2f}</div><div class="{'kpi-change-up' if pdelta>=0 else 'kpi-change-down'}">{da} {abs(dpct):.3f}%</div></div>
                <div class="kpi-card"><div class="kpi-label">RSI (14)</div><div class="kpi-value" style="color:{rc};">{'%.1f'%rsi_v if rsi_v is not None else '—'}</div><div style="font-size:11px;color:#64748b;">{('Overbought' if rsi_v>=70 else ('Oversold' if rsi_v<=30 else 'Neutral')) if rsi_v else f'{max(0,MIN_RSI-n)} pts left'}</div></div>
                <div class="kpi-card"><div class="kpi-label">MACD</div><div class="kpi-value" style="color:{mc if macd_v else '#334155'};">{'%.2f'%macd_v if macd_v is not None else '—'}</div><div style="font-size:11px;color:#64748b;">{'Signal: %.2f'%msig_v if msig_v else f'{max(0,MIN_MACD-n)} pts left'}</div></div>
                <div class="kpi-card"><div class="kpi-label">SESSION VWAP</div><div class="kpi-value">${last['vwap']:,.2f}</div><div style="font-size:11px;color:#64748b;">{'Above ↑' if price>last['vwap'] else 'Below ↓'} VWAP</div></div>
                <div class="kpi-card"><div class="kpi-label">BB Width</div><div class="kpi-value">{'%.2f%%'%bbw_v if bbw_v is not None else '—'}</div><div style="font-size:11px;color:#64748b;">{'Vol: %.3f%%'%vol_v if vol_v else f'{max(0,MIN_BB-n)} pts left'}</div></div>
                </div>""", unsafe_allow_html=True)

            with chart_ph.container():
                st.plotly_chart(build_charts(df), use_container_width=True,
                                config={'displayModeBar': True, 'displaylogo': False,
                                        'modeBarButtonsToRemove': ['select2d', 'lasso2d']})

            report_items = generate_report(df)
            bias         = compute_net_bias(report_items, df)
            report_html  = build_report_html(report_items, bias, n)
            report_ph.empty()
            with report_ph.container():
                components.html(report_html, height=max(350, len(report_items) * 65 + 160), scrolling=False)

        elif n > 0:
            status_ph.markdown(f"<div class='status-waiting'>AGGREGATING DATA... {n} / 2 data points. Standby.</div>", unsafe_allow_html=True)
        
        time.sleep(1)

if __name__ == "__main__":
    main()
