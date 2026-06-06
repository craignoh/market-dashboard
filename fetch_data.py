"""
Daily market indicator fetcher
Runs via GitHub Actions every day at 00:00 UTC (09:00 KST)
Saves output to data/indicators.json
"""

import json
import os
import sys
from datetime import datetime, timedelta
import requests
import yfinance as yf

# ── FRED API key (set as GitHub Actions secret: FRED_API_KEY) ──────────────
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# ── Helpers ────────────────────────────────────────────────────────────────

def fred_latest(series_id: str) -> float | None:
    """Fetch the most recent observation from FRED."""
    if not FRED_API_KEY:
        print(f"  [WARN] FRED_API_KEY not set, skipping {series_id}")
        return None
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 5,
    }
    try:
        r = requests.get(FRED_BASE, params=params, timeout=10)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        for o in obs:
            if o["value"] != ".":
                return float(o["value"])
    except Exception as e:
        print(f"  [ERROR] FRED {series_id}: {e}")
    return None


def fred_history(series_id: str, days: int = 35) -> list[dict]:
    """Fetch last N days of observations from FRED."""
    if not FRED_API_KEY:
        return []
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "asc",
        "observation_start": start,
    }
    try:
        r = requests.get(FRED_BASE, params=params, timeout=10)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        return [{"date": o["date"], "value": float(o["value"])}
                for o in obs if o["value"] != "."]
    except Exception as e:
        print(f"  [ERROR] FRED history {series_id}: {e}")
    return []


def yf_latest(ticker: str) -> float | None:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception as e:
        print(f"  [ERROR] yfinance {ticker}: {e}")
    return None


def yf_history(ticker: str, days: int = 35) -> list[dict]:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=f"{days}d")
        return [
            {"date": str(d.date()), "value": round(float(v), 2)}
            for d, v in zip(hist.index, hist["Close"])
        ]
    except Exception as e:
        print(f"  [ERROR] yfinance history {ticker}: {e}")
    return []


def fear_greed_latest() -> dict | None:
    """Alternative.me Crypto Fear & Greed — free, stable."""
    try:
        r = requests.get(
            "https://api.alternative.me/fng/?limit=1&format=json", timeout=10
        )
        r.raise_for_status()
        data = r.json()["data"][0]
        return {
            "value": int(data["value"]),
            "classification": data["value_classification"],
        }
    except Exception as e:
        print(f"  [ERROR] Fear&Greed: {e}")
    return None


def fear_greed_history(days: int = 35) -> list[dict]:
    try:
        r = requests.get(
            f"https://api.alternative.me/fng/?limit={days}&format=json", timeout=10
        )
        r.raise_for_status()
        items = r.json()["data"]
        return [
            {
                "date": datetime.utcfromtimestamp(int(i["timestamp"])).strftime("%Y-%m-%d"),
                "value": int(i["value"]),
                "classification": i["value_classification"],
            }
            for i in reversed(items)
        ]
    except Exception as e:
        print(f"  [ERROR] Fear&Greed history: {e}")
    return []


def put_call_ratio() -> float | None:
    """
    CBOE total put/call ratio via Yahoo Finance ticker ^PCI is not available.
    We use the CBOE equity P/C ratio via yfinance as a proxy.
    Falls back to None if unavailable.
    """
    try:
        # CBOE does not expose P/C via yfinance; scrape CBOE data page
        url = "https://www.cboe.com/publish/scheduledtask/mktdata/cboesymboldata/options_put_call_ratios.csv"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        # last data line
        for line in reversed(lines):
            parts = line.split(",")
            if len(parts) >= 4:
                try:
                    return round(float(parts[3]), 2)  # Total P/C ratio column
                except ValueError:
                    continue
    except Exception as e:
        print(f"  [WARN] Put/Call CBOE: {e} — skipping")
    return None


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.utcnow().isoformat()}] Fetching market indicators...")

    today = datetime.utcnow().strftime("%Y-%m-%d")

    # ── Current snapshot ───────────────────────────────────────────────────
    print("  Fetching index prices (yfinance)...")
    nasdaq    = yf_latest("^IXIC")
    sp500     = yf_latest("^GSPC")
    djia      = yf_latest("^DJI")
    vix       = yf_latest("^VIX")
    tnx       = yf_latest("^TNX")   # 10-yr Treasury yield ×10 in Yahoo

    print("  Fetching FRED series...")
    fed_rate  = fred_latest("FEDFUNDS")          # Fed Funds Rate
    hy_spread = fred_latest("BAMLH0A0HYM2")      # HY OAS spread
    t2y       = fred_latest("DGS2")              # 2-yr Treasury yield
    t10y      = fred_latest("DGS10")             # 10-yr Treasury yield

    yield_curve = None
    if t10y is not None and t2y is not None:
        yield_curve = round(t10y - t2y, 3)

    # Use FRED 10y if yfinance TNX unavailable
    ten_yr = t10y if t10y else (round(tnx / 10, 3) if tnx else None)

    print("  Fetching Fear & Greed (alternative.me)...")
    fg = fear_greed_latest()

    print("  Fetching Put/Call ratio (CBOE)...")
    pc_ratio = put_call_ratio()

    # ── 35-day history for sparklines ─────────────────────────────────────
    print("  Fetching 35-day history...")
    history = {
        "nasdaq":      yf_history("^IXIC", 35),
        "sp500":       yf_history("^GSPC", 35),
        "djia":        yf_history("^DJI",  35),
        "vix":         yf_history("^VIX",  35),
        "tnx":         fred_history("DGS10", 40),
        "hy_spread":   fred_history("BAMLH0A0HYM2", 40),
        "yield_curve": [],   # computed below
        "fear_greed":  fear_greed_history(35),
    }

    # Compute 2s10s history from FRED
    t2_hist  = fred_history("DGS2",  40)
    t10_hist = fred_history("DGS10", 40)
    t2_map   = {d["date"]: d["value"] for d in t2_hist}
    history["yield_curve"] = [
        {"date": d["date"], "value": round(d["value"] - t2_map[d["date"]], 3)}
        for d in t10_hist if d["date"] in t2_map
    ]

    # ── Risk score (0-100) ─────────────────────────────────────────────────
    risk = 0
    if vix:
        if vix > 45: risk += 30
        elif vix > 35: risk += 22
        elif vix > 25: risk += 14
        elif vix > 18: risk += 7
    if fg:
        fgv = fg["value"]
        if fgv < 20: risk += 25
        elif fgv < 35: risk += 15
        elif fgv < 45: risk += 8
    if hy_spread:
        if hy_spread > 8: risk += 20
        elif hy_spread > 6: risk += 14
        elif hy_spread > 4: risk += 7
    if yield_curve is not None:
        if yield_curve < -0.3: risk += 15
        elif yield_curve < 0:  risk += 8
        elif yield_curve < 0.3: risk += 4
    risk = min(risk, 100)

    risk_label = (
        "위험 — 급락 가능성 높음" if risk >= 70 else
        "경고 — 복합 신호 감지" if risk >= 50 else
        "주의 — 일부 지표 이상" if risk >= 30 else
        "안전 — 리스크 낮음"
    )

    # ── Assemble output ────────────────────────────────────────────────────
    output = {
        "updated_at": today,
        "updated_kst": (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST"),
        "snapshot": {
            "nasdaq":      nasdaq,
            "sp500":       sp500,
            "djia":        djia,
            "vix":         vix,
            "ten_yr":      ten_yr,
            "fed_rate":    fed_rate,
            "hy_spread":   hy_spread,
            "yield_curve": yield_curve,
            "fear_greed":  fg,
            "put_call":    pc_ratio,
        },
        "risk_score": risk,
        "risk_label": risk_label,
        "history":    history,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/indicators.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  Done. Risk score: {risk}/100 ({risk_label})")
    print(f"  Saved to data/indicators.json")


if __name__ == "__main__":
    main()
