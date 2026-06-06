import json
import os
from datetime import datetime, timedelta
import requests

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

def fred_latest(series_id):
    if not FRED_API_KEY:
        return None
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 5,
    }
    try:
        r = requests.get(FRED_BASE, params=params, timeout=15)
        r.raise_for_status()
        for o in r.json().get("observations", []):
            if o["value"] != ".":
                return float(o["value"])
    except Exception as e:
        print(f"  [ERROR] FRED {series_id}: {e}")
    return None

def fred_history(series_id, days=40):
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
        r = requests.get(FRED_BASE, params=params, timeout=15)
        r.raise_for_status()
        return [{"date": o["date"], "value": float(o["value"])}
                for o in r.json().get("observations", [])
                if o["value"] != "."]
    except Exception as e:
        print(f"  [ERROR] FRED history {series_id}: {e}")
    return []

def stooq_history(ticker, days=40):
    """stooq.com — yfinance 대체, 자동화 환경에서 안정적"""
    end = datetime.utcnow().strftime("%Y%m%d")
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={ticker}&d1={start}&d2={end}&i=d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        result = []
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) >= 5 and parts[4] != "null":
                try:
                    result.append({
                        "date": parts[0],
                        "value": round(float(parts[4]), 2)
                    })
                except ValueError:
                    continue
        return result
    except Exception as e:
        print(f"  [ERROR] stooq {ticker}: {e}")
    return []

def stooq_latest(ticker):
    data = stooq_history(ticker, days=7)
    if data:
        return data[-1]["value"]
    return None

def fear_greed_latest():
    try:
        r = requests.get(
            "https://api.alternative.me/fng/?limit=1&format=json", timeout=15)
        r.raise_for_status()
        d = r.json()["data"][0]
        return {"value": int(d["value"]), "classification": d["value_classification"]}
    except Exception as e:
        print(f"  [ERROR] Fear&Greed: {e}")
    return None

def fear_greed_history(days=35):
    try:
        r = requests.get(
            f"https://api.alternative.me/fng/?limit={days}&format=json", timeout=15)
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

def main():
    print(f"[{datetime.utcnow().isoformat()}] Fetching market indicators...")
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # stooq 티커: ^NDX=나스닥, ^SPX=S&P500, ^DJI=다우, ^VIX=VIX
    print("  Fetching indices via stooq...")
    nasdaq = stooq_latest("^nasdaq")
    sp500  = stooq_latest("^spx500")
    djia   = stooq_latest("^dji")
    vix    = stooq_latest("vix.cboe")

    print("  Fetching FRED series...")
    fed_rate  = fred_latest("FEDFUNDS")
    hy_spread = fred_latest("BAMLH0A0HYM2")
    t2y       = fred_latest("DGS2")
    t10y      = fred_latest("DGS10")

    yield_curve = round(t10y - t2y, 3) if t10y and t2y else None
    ten_yr = t10y

    print("  Fetching Fear & Greed...")
    fg = fear_greed_latest()

    print("  Fetching 35-day history...")
    nasdaq_h = stooq_history("^nasdaq", 40)
    sp500_h  = stooq_history("^spx500", 40)
    djia_h   = stooq_history("^dji", 40)
    vix_h    = stooq_history("vix.cboe", 40)
    tnx_h    = fred_history("DGS10", 40)
    hy_h     = fred_history("BAMLH0A0HYM2", 40)
    fg_h     = fear_greed_history(35)

    t2_h  = fred_history("DGS2", 40)
    t10_h = fred_history("DGS10", 40)
    t2_map = {d["date"]: d["value"] for d in t2_h}
    yc_h   = [{"date": d["date"], "value": round(d["value"] - t2_map[d["date"]], 3)}
               for d in t10_h if d["date"] in t2_map]

    # 리스크 점수
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
        "경고 — 복합 신호 감지"   if risk >= 50 else
        "주의 — 일부 지표 이상"   if risk >= 30 else
        "안전 — 리스크 낮음"
    )

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
            "put_call":    None,
        },
        "risk_score": risk,
        "risk_label": risk_label,
        "history": {
            "nasdaq":      nasdaq_h,
            "sp500":       sp500_h,
            "djia":        djia_h,
            "vix":         vix_h,
            "tnx":         tnx_h,
            "hy_spread":   hy_h,
            "yield_curve": yc_h,
            "fear_greed":  fg_h,
        },
    }

    os.makedirs("data", exist_ok=True)
    with open("data/indicators.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  Done. Risk: {risk}/100 ({risk_label})")
    print(f"  NASDAQ={nasdaq}, SP500={sp500}, VIX={vix}")

if __name__ == "__main__":
    main()
