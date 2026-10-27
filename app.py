from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import data
from engine import simulate, signal

st.set_page_config(page_title="CL Quant Research", layout="wide")
st.title("WTI / CL Quant Research")
st.warning("Experimental, unvalidated model. Simulation shares are not proven trading odds. Free quotes may be delayed.")

with st.sidebar:
    mode = st.radio("Data mode", ["Synthetic demo", "Public data"])
    horizon = st.selectbox("Trading hours", [1, 3, 5, 23, 115, 483], index=4)
    st.caption("23 / 115 / 483 hours represent 1 / 5 / 21 trading sessions.")
    capacity = st.number_input("Assumed Cushing capacity, million bbl", 1., 200., 76.)
    expiry = st.number_input("Assumed days to contract expiry", 0., 365., 20.)
    st.caption("Capacity and expiry are assumptions requiring verification.")
    with st.expander("Dated manual observations"):
        use_freight = st.checkbox("I have an observed VLCC freight z-score")
        freight = st.number_input("Freight z-score", -8., 8., 0.)
        use_curve = st.checkbox("I have an observed futures slope")
        curve = st.number_input("Annual slope, USD/bbl/year", -500., 500., 0.)
        observed_date = st.date_input("Observation date, UTC")
        st.caption("Positive slope means contango. Do not mark invented values as observed.")
    verified = st.checkbox("I verified capacity, expiry, factors and the EIA schedule; coefficients remain unvalidated.")
    seed = st.number_input("Simulation seed", 0, 2147483647, 42)
    if st.button("Clear source caches"):
        st.cache_data.clear()

@st.cache_data(ttl=21600)
def factors():
    return data.public_factors()

@st.cache_data(ttl=60)
def latest_quote():
    return data.quote()

def market_open(at):
    local = at.astimezone(ZoneInfo("America/New_York"))
    d, h = local.weekday(), local.hour
    return (d==6 and h>=18) or (d<4 and h!=17) or (d==4 and h<17)

def trading_hours(start, end):
    total = 0.
    while start < end:
        stop = min(end, start.replace(minute=0, second=0, microsecond=0)+timedelta(hours=1))
        if market_open(start):
            total += (stop-start).total_seconds()/3600
        start = stop
    return total

@st.fragment(run_every="60s")
def dashboard():
    now = datetime.now(timezone.utc)
    is_demo = mode=="Synthetic demo"
    with st.spinner("Loading and simulating..."):
        inputs, history, warnings = data.demo(int(seed)) if is_demo else factors()
        if not is_demo:
            inputs["price"] = latest_quote()
            stamp = datetime.combine(observed_date, datetime.min.time(), timezone.utc)
            if use_freight:
                inputs["freight"] = data.observation(freight, stamp, "User-supplied VLCC z-score")
            if use_curve:
                inputs["curve"] = data.observation(curve, stamp, "User-supplied curve slope")
        if is_demo:
            st.error("SYNTHETIC DEMO: all inputs and outputs are generated.")
        if inputs["price"]["value"] is None:
            st.subheader("HOLD - current CL quote unavailable")
            st.write("Switch to Synthetic demo to explore without network access.")
            st.write(warnings)
            return
        local = now.astimezone(ZoneInfo("America/New_York"))
        release = (local+timedelta(days=(2-local.weekday())%7)).replace(hour=10, minute=30, second=0, microsecond=0)
        if release<=local:
            release += timedelta(days=7)
        first_event = trading_hours(now, release)
        events = [first_event+115*k for k in range(6) if 0<first_event+115*k<=horizon]
        try:
            sim = simulate(inputs, history, capacity, expiry, float(horizon),
                           seed=int(seed), events=events)
            result = signal(inputs, history, sim, now, capacity, expiry,
                            is_demo, verified)
        except ValueError as exc:
            st.error("HOLD - "+str(exc))
            return
    cols = st.columns(3)
    cols[0].metric("CL quote, USD/bbl", f'{inputs["price"]["value"]:.2f}')
    cols[1].metric("Arithmetic sigma, USD/bbl/sqrt(year)", f'{sim["sigma"]:.2f}')
    cols[2].metric("90% model endpoint range", f'{result["low"]:.2f} to {result["high"]:.2f}')
    st.caption(f'Quote timestamp: {inputs["price"]["date"]}. Public refresh checks every 60 seconds; zero-delay data are not guaranteed.')
    st.subheader(("DEMO - " if is_demo else "Unvalidated model action - ")+result["action"])
    st.write("; ".join(result["blockers"]) if result["blockers"] else
             "Model distribution and completed-history band rule. No established profitable edge.")
    st.write(f'Model terminal shares after assumed $0.04/bbl costs: Up {result["up"]:.1%}; Down {result["down"]:.1%}. Remaining paths are inside the cost band.')
    if result["tp"] is not None:
        st.write(f'Illustrative TP ${result["tp"]:.2f}; SL ${result["sl"]:.2f} per barrel.')
    else:
        st.write("TP and SL withheld while HOLD is active.")
    q = sim["bands"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sim["grid"], y=q[:,2], name="95th percentile", line=dict(width=0)))
    fig.add_trace(go.Scatter(x=sim["grid"], y=q[:,0], name="5th percentile",
                            line=dict(width=0), fill="tonexty"))
    for i in range(15):
        fig.add_trace(go.Scatter(x=sim["grid"], y=sim["samples"][:,i],
                                opacity=.25, showlegend=False, line=dict(width=1)))
    fig.add_trace(go.Scatter(x=sim["grid"], y=q[:,1], name="Median"))
    fig.update_layout(title="Arithmetic price scenarios - negative prices permitted",
                      xaxis_title="Trading hours", yaxis_title="USD/barrel")
    st.plotly_chart(fig, use_container_width=True)
    left, right = st.columns(2)
    vf = go.Figure(go.Scatter(x=sim["grid"], y=np.sqrt(sim["variance"])))
    vf.update_layout(title="Stochastic volatility", xaxis_title="Trading hours",
                     yaxis_title="USD/bbl/sqrt(year)")
    left.plotly_chart(vf, use_container_width=True)
    inventory = go.Figure()
    for i, label in enumerate(["5th percentile", "Median", "95th percentile"]):
        inventory.add_trace(go.Scatter(x=sim["grid"], y=sim["inventory"][:,i], name=label))
    inventory.add_hline(y=capacity, line_color="red", annotation_text="Assumed capacity")
    inventory.update_layout(title="Inventory scenarios, not EIA forecasts",
                            yaxis_title="Million barrels", xaxis_title="Trading hours")
    right.plotly_chart(inventory, use_container_width=True)
    with st.expander("Data provenance and assumptions"):
        st.dataframe(pd.DataFrame([dict(factor=k, **v) for k,v in inputs.items()]))
        st.write(warnings)
        st.write("Weekly dates are reporting periods, not exact publication timestamps. Freight and curve are never silently fabricated. Missing factors use neutral plotting assumptions and block public actions.")
        st.write("EIA schedule assumes Wednesday 10:30 New York and regular weekly spacing. Holiday exceptions require verification. Capacity, expiry, jumps, factor coefficients, TP and SL remain assumptions.")
    snapshot = dict(mode=mode, calculated_at=now.isoformat(), inputs=inputs,
                    capacity=capacity, expiry_days=expiry, horizon=horizon,
                    seed=int(seed), signal=result)
    st.download_button("Download research snapshot",
                       json.dumps(snapshot, default=str, indent=2, allow_nan=False),
                       "cl-research.json", "application/json")

dashboard()
st.caption("No broker connection. No guaranteed fills or returns. SELL NOW is a bearish model label, not a position-aware exit. Free hosting and data availability can change.")