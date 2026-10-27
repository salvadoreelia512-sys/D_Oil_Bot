from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
import numpy as np
import pandas as pd
import requests
import yfinance as yf

NAMES = ["price", "rate", "dollar", "inventory", "utilization",
         "crack", "freight", "curve", "surprise"]

def observation(value, date, source, status="observed"):
    stamp = pd.Timestamp(date)
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    number = float(value)
    if not np.isfinite(number):
        raise ValueError("Invalid source number")
    return dict(value=number, date=stamp.to_pydatetime(),
                source=source, status=status)

def empty():
    return {name: dict(value=None, date=None, source="Unavailable",
                       status="missing") for name in NAMES}

def yahoo(symbol, period, interval="1d"):
    frame = yf.download(symbol, period=period, interval=interval,
                        auto_adjust=False, progress=False,
                        threads=False, timeout=10)
    if frame.empty:
        raise ValueError("No Yahoo data")
    series = frame["Close"]
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    return pd.to_numeric(series, errors="coerce").dropna().sort_index()

def quote():
    try:
        s = yahoo("CL=F", "5d", "1m")
        return observation(s.iloc[-1], s.index[-1],
                           "Yahoo CL=F; may be delayed")
    except Exception:
        return empty()["price"]

def eia(code):
    url = f"https://www.eia.gov/dnav/pet/hist_xls/{code}.xls"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    frame = pd.read_excel(BytesIO(response.content), sheet_name=1,
                          header=2).iloc[:, :2]
    frame.columns = ["date", "value"]
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", utc=True)
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna().drop_duplicates("date").sort_values("date")
    if len(frame) < 30:
        raise ValueError("Insufficient EIA history")
    return frame.set_index("date")["value"]

def public_factors():
    inputs, history, warnings = empty(), [], []
    today = datetime.now(timezone.utc).date()
    def attempt(label, fn):
        try:
            fn()
        except Exception as exc:
            warnings.append(f"{label}: unavailable ({type(exc).__name__})")
    def prices():
        nonlocal history
        s = yahoo("CL=F", "3y")
        s = s[s.index.date < today]
        history = s.astype(float).tolist()
    def rates():
        r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv",
                         params={"id": "DFII10"}, timeout=12)
        r.raise_for_status()
        s = pd.to_numeric(pd.read_csv(StringIO(r.text), index_col=0).iloc[:, 0],
                          errors="coerce").dropna()
        inputs["rate"] = observation(s.iloc[-1], s.index[-1],
                                     "FRED DFII10 real yield, percent")
    def dollars():
        s = yahoo("DX-Y.NYB", "6mo")
        s = s[s.index.date < today]
        if len(s) < 22:
            raise ValueError("Insufficient DXY history")
        inputs["dollar"] = observation(
            12*np.log(s.iloc[-1]/s.iloc[-22]), s.index[-1],
            "Yahoo DXY; annualized 21-session log change")
    def stocks():
        s = eia("W_EPC0_SAX_YCUOK_MBBLw") / 1000
        inputs["inventory"] = observation(
            s.iloc[-1], s.index[-1], "EIA Cushing; million barrels")
        changes = s.diff().dropna()
        prior = changes.iloc[-27:-1]
        surprise = (changes.iloc[-1]-prior.tail(8).mean()) / max(.1, prior.std())
        inputs["surprise"] = observation(
            surprise, s.index[-1],
            "Own forecast residual; NOT analyst consensus", "proxy")
    def utilization():
        s = eia("WPULEUS3w")
        inputs["utilization"] = observation(
            s.iloc[-1], s.index[-1], "EIA refinery utilization, percent")
    def crack():
        aligned = pd.concat([yahoo(t, "3mo")
                             for t in ["CL=F", "RB=F", "HO=F"]],
                            axis=1, join="inner").dropna()
        aligned = aligned[aligned.index.date < today]
        cl, rb, ho = aligned.iloc[-1]
        inputs["crack"] = observation(
            42*(2*rb+ho)/3-cl, aligned.index[-1],
            "Date-aligned Yahoo 3-2-1 crack, USD/bbl; delivery mismatch possible",
            "proxy")
    for label, function in [
        ("Daily CL", prices), ("Real yield", rates), ("DXY", dollars),
        ("Cushing", stocks), ("Refinery utilization", utilization),
        ("Crack spread", crack)
    ]:
        attempt(label, function)
    return inputs, history, warnings

def demo(seed=42):
    rng = np.random.default_rng(seed)
    now = datetime.now(timezone.utc)
    history = (75+np.cumsum(rng.normal(0, 1.4, 600))).tolist()
    values = [history[-1], 1.7, .03, 48, 90, 20, .4, 2, .5]
    inputs = {name: observation(v, now, "SYNTHETIC DEMO", "mock")
              for name, v in zip(NAMES, values)}
    return inputs, history, []