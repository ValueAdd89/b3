import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from engine import PolygonTradingEngine
import time

st.set_page_config(page_title="Atlas Equity Suite", layout="wide")
st.title("🏛️ Atlas Professional Stock Liquidity Dashboard")

# --- SECURE CREDENTIAL CHECK ---
st.sidebar.subheader("Configuration Panel")
poly_api_key = st.sidebar.text_input("Enter Polygon.io API Key", type="password")
selected_stock = st.sidebar.selectbox("Select Equity Ticker", ["NVDA", "AAPL", "TSLA", "AMD", "SPY", "QQQ"])

if not poly_api_key:
    st.info("🔑 Please enter your private Polygon.io key in the left sidebar to unlock the equities streaming pipeline.")
    st.stop()

# --- INSTANTIATE BACKGROUND CLIENT ---
if "poly_engine" not in st.session_state or st.session_state.get("current_ticker") != selected_stock:
    # If ticker changes, reset engine configuration seamlessly
    st.session_state.poly_engine = PolygonTradingEngine(api_key=poly_api_key, symbol=selected_stock, max_history=60)
    st.session_state.poly_engine.start()
    st.session_state.current_ticker = selected_stock
    time.sleep(1.5)

engine = st.session_state.poly_engine
history, live_bids, live_asks, current_price, footprint, alerts = engine.get_snapshot()

if current_price == 0:
    st.warning(f"Connecting to Polygon.io clusters. Awaiting first matching trades or quotes for {selected_stock}...")
    time.sleep(1)
    st.rerun()

# --- DISPLAY STREAMING DASHBOARD PANELS ---
tab1, tab2 = st.tabs(["📊 Real-Time Liquidity Maps", "🚨 Tape Block Feed"])

with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("NBBO Spread History Tracking")
        times, prices, volumes, types = [], [], [], []
        for frame in history:
            for p, q in frame["bids"].items():
                times.append(frame["time"]); prices.append(p); volumes.append(q); types.append("Bid")
            for p, q in frame["asks"].items():
                times.append(frame["time"]); prices.append(p); volumes.append(q); types.append("Ask")
        
        if times:
            df = pd.DataFrame({"Time": times, "Price": prices, "Volume": volumes, "Type": types})
            fig = go.Figure()
            # Plot Bid spread layer
            b_df = df[df["Type"]=="Bid"]
            fig.add_trace(go.Scatter(x=b_df["Time"], y=b_df["Price"], mode="markers+lines", marker=dict(size=5, color="green"), name="National Best Bid"))
            # Plot Ask spread layer
            a_df = df[df["Type"]=="Ask"]
            fig.add_trace(go.Scatter(x=a_df["Time"], y=a_df["Price"], mode="markers+lines", marker=dict(size=5, color="red"), name="National Best Ask"))
            
            fig.update_layout(template="plotly_dark", height=420, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig, use_container_width=True)
            
    with col2:
        st.subheader("Intraday Share Footprint")
        if footprint:
            fp_prices = sorted(list(footprint.keys()))[-15:] # Capture last 15 active pricing bands
            bids_f = [footprint[p]["Bid_Vol"] for p in fp_prices]
            asks_f = [footprint[p]["Ask_Vol"] for p in fp_prices]
            
            fig_fp = go.Figure()
            fig_fp.add_trace(go.Bar(y=fp_prices, x=bids_f, orientation='h', name="Aggressive Sells", marker_color='red'))
            fig_fp.add_trace(go.Bar(y=fp_prices, x=asks_f, orientation='h', name="Aggressive Buys", marker_color='green'))
            fig_fp.update_layout(barmode='relative', template="plotly_dark", height=420, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig_fp, use_container_width=True)
        else:
            st.caption("Listening for raw transaction volume prints...")

with tab2:
    st.subheader(f"Whale Alert Streaming Tape — {selected_stock}")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Unified Share Midpoint", f"${current_price:,.2f}")
        total_b = sum(live_bids.values())
        total_a = sum(live_asks.values())
        st.metric("Immediate Best Bid/Ask Sizes", f"{total_b:,} Lots vs {total_a:,} Lots")
    with c2:
        if alerts:
            for a in reversed(alerts):
                st.warning(f"**{a['time']}** | {a['msg']}")
        else:
            st.info("Monitoring continuous tape strings for large block prints exceeding 10,000 shares...")

# Run loops every 1.5 seconds to balance UI rendering load
time.sleep(1.5)
st.rerun()