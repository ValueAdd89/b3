import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from engine import AdvancedTradingEngine
import time

st.set_page_config(page_title="Atlas Trading Suite", layout="wide", initial_sidebar_state="collapsed")
st.title("⚡ Atlas Multi-Dimensional Order Flow Engine")

# Initialize Engine
if "adv_engine" not in st.session_state:
    st.session_state.adv_engine = AdvancedTradingEngine(symbol="btcusdt", max_history=60)
    st.session_state.adv_engine.start()
    time.sleep(1.5)

engine = st.session_state.adv_engine
history, live_bids, live_asks, current_price, footprint, alerts = engine.get_snapshot()

if current_price == 0:
    st.warning("Connecting to global WebSockets exchange infrastructure...")
    time.sleep(1)
    st.rerun()

# Layout Configuration Matrix
tab1, tab2, tab3 = st.tabs(["📊 Orderflow & Footprint Profile", "🎛️ Option Gamma Position Maps", "🚨 Real-Time Tape Alerts"])

# --- TAB 1: FOOTPRINT & ORDERFLOW ---
with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Microsecond Price Heatmap")
        times, prices, volumes, types = [], [], [], []
        for frame in history:
            for p, q in frame["bids"].items():
                times.append(frame["time"]); prices.append(p); volumes.append(q); types.append("Bid")
            for p, q in frame["asks"].items():
                times.append(frame["time"]); prices.append(p); volumes.append(q); types.append("Ask")
        
        if times:
            df = pd.DataFrame({"Time": times, "Price": prices, "Volume": volumes, "Type": types})
            fig = go.Figure()
            # Bids Grid Overlay
            b_df = df[df["Type"]=="Bid"]
            fig.add_trace(go.Scatter(x=b_df["Time"], y=b_df["Price"], mode="markers", marker=dict(size=6, color=b_df["Volume"], colorscale="Greens", showscale=False), name="Bids"))
            # Asks Grid Overlay
            a_df = df[df["Type"]=="Ask"]
            fig.add_trace(go.Scatter(x=a_df["Time"], y=a_df["Price"], mode="markers", marker=dict(size=6, color=a_df["Volume"], colorscale="Reds", showscale=False), name="Asks"))
            
            fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0), yaxis=dict(range=[current_price*0.999, current_price*1.001]))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Volume Footprint Clusters")
        # Format footprints into visual bid-ask components
        if footprint:
            fp_prices = sorted(list(footprint.keys()))[-12:] # Show top 12 active bands
            bids_f = [footprint[p]["Bid_Vol"] for p in fp_prices]
            asks_f = [footprint[p]["Ask_Vol"] for p in fp_prices]
            
            fig_fp = go.Figure()
            fig_fp.add_trace(go.Bar(y=fp_prices, x=bids_f, orientation='h', name="Aggressive Sells (Bid Side)", marker_color='red'))
            fig_fp.add_trace(go.Bar(y=fp_prices, x=asks_f, orientation='h', name="Aggressive Buys (Ask Side)", marker_color='green'))
            fig_fp.update_layout(barmode='relative', template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig_fp, use_container_width=True)
        else:
            st.info("Awaiting execution transactions to populate clusters...")

# --- TAB 2: OPTIONS DEALER POSITIONING (GEX) ---
with tab2:
    st.subheader("Systemic Market Maker Gamma Configuration")
    df_gex = engine.calculate_gamma_exposure()
    
    if not df_gex.empty:
        # Locate systemic parameters
        zero_gamma_idx = np.abs(df_gex["GEX_Billions"]).idxmin()
        zero_gamma_strike = df_gex.loc[zero_gamma_idx, "Strike"]
        
        c1, c2 = st.columns([1, 3])
        with c1:
            st.metric("Estimated Zero Gamma Threshold", f"${zero_gamma_strike:,.2f}")
            st.info("💡 Above Zero Gamma, volatility mean-reverts (stable). Below Zero Gamma, market-maker positioning forces aggressive hedging (high volatility).")
            
        with c2:
            fig_gex = go.Figure()
            # Dynamic Bar charting color mapped to risk metrics
            colors = ['green' if x >= 0 else 'red' for x in df_gex["GEX_Billions"]]
            fig_gex.add_trace(go.Bar(x=df_gex["Strike"], y=df_gex["GEX_Billions"], marker_color=colors, name="Net GEX ($)"))
            fig_gex.add_vline(x=current_price, line_dash="dash", line_color="cyan", annotation_text="Spot Price")
            fig_gex.update_layout(template="plotly_dark", height=400, xaxis_title="Options Strike Level ($)", yaxis_title="Net Open Interest Gamma ($ Exposure)")
            st.plotly_chart(fig_gex, use_container_width=True)

# --- TAB 3: INSTITUTIONAL TAPE TRACKER ---
with tab3:
    st.subheader("Algorithmic Whales & Iceberg Feed Alerts")
    if alerts:
        for a in reversed(alerts):
            # Render visual alert boxes based on algorithmic category parameters
            if "ICEBERG" in a["type"]:
                st.toast(f"Iceberg Detected: {a['msg']}")
                st.error(f"**{a['time']}** | **{a['type']}** — {a['msg']}")
            else:
                st.warning(f"**{a['time']}** | **{a['type']}** — {a['msg']}")
    else:
        st.info("Scanning execution tape data for abnormal institutional block trades...")

# Re-render loop cycle parameter
time.sleep(1)
st.rerun()