import json
import os
from datetime import datetime, timedelta
import requests

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_BASE    = "https://api.stlouisfed.org/fred/series/observations"

def fred_latest(series_id):
    if not FRED_API_KEY:
        return None
    params = {"series_id": series_id, "api_key": FRED_API_KEY,
              "file_type": "json", "sort_order": "desc", "limit": 5}
    try:
        r = requests.get(FRED_BASE, params=params, timeout=15)
        r.raise_for_status()
        for o in r.json().get("observations", []):
            if o["value"] != ".":
                return float(o["value"])
    except Exception as e:
        print(f"  [ERROR] FRED {series_id}: {e}")
    return None

def fred_history(series_id, days=250):
    if not FRED_API_KEY:
        return []
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {"series_id": series_id, "api_key": FRED_API_KEY,
              "file_type": "json", "sort_order": "asc", "observation_start": start}
    try:
        r = requests.get(FRED_BASE, params=params, timeout=15)
        r.raise_for_status()
        return [{"date": o["date"], "value": float(o["value"])}
                for o in r.json().get("observations", []) if o["value"] != "."]
    except Exception as e:
        print(f"  [ERROR] FRED history {series_id}: {e}")
    return []

def calc_rsi(values, period=14):
    """RSI 계산 (단순 이동평균 방식)"""
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        diff = values[i] - values[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calc_ma_deviation(values, period=200):
    """현재가 대비 N일 이동평균 괴리율 (%)"""
    if len(values) < period:
        return None
    ma = sum(values[-period:]) / period
    current = values[-1]
    return round((current - ma) / ma * 100, 2)

def calc_ma_deviation_50(values):
    return calc_ma_deviation(values, 50)

def fear_greed_latest():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1&format=json", timeout=15)
        r.raise_for_status()
        d = r.json()["data"][0]
        return {"value": int(d["value"]), "classification": d["value_classification"]}
    except Exception as e:
        print(f"  [ERROR] Fear&Greed: {e}")
    return None

def fear_greed_history(days=45):
    try:
        r = requests.get(f"https://api.alternative.me/fng/?limit={days}&format=json", timeout=15)
        r.raise_for_status()
        items = r.json()["data"]
        return [{"date": datetime.utcfromtimestamp(int(i["timestamp"])).strftime("%Y-%m-%d"),
                 "value": int(i["value"]), "classification": i["value_classification"]}
                for i in reversed(items)]
    except Exception as e:
        print(f"  [ERROR] Fear&Greed history: {e}")
    return []

def main():
    print(f"[{datetime.utcnow().isoformat()}] Fetching market indicators...")
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # ── 지수 (200일 이평선 계산을 위해 250일치 수집) ──────────────────
    print("  Fetching indices via FRED (250 days)...")
    nasdaq_h = fred_history("NASDAQCOM", 350)
    sp500_h  = fred_history("SP500",     350)
    djia_h   = fred_history("DJIA",      350)
    vix_h    = fred_history("VIXCLS",    45)

    nasdaq_vals = [d["value"] for d in nasdaq_h]
    sp500_vals  = [d["value"] for d in sp500_h]
    djia_vals   = [d["value"] for d in djia_h]

    nasdaq = nasdaq_vals[-1] if nasdaq_vals else None
    sp500  = sp500_vals[-1]  if sp500_vals  else None
    djia   = djia_vals[-1]   if djia_vals   else None
    vix    = vix_h[-1]["value"] if vix_h    else None

    # ── RSI 계산 ───────────────────────────────────────────────────────
    print("  Calculating RSI...")
    rsi_nasdaq = calc_rsi(nasdaq_vals)
    rsi_sp500  = calc_rsi(sp500_vals)
    print(f"  RSI NASDAQ={rsi_nasdaq}, SP500={rsi_sp500}")

    # ── 이동평균 괴리율 ────────────────────────────────────────────────
    print("  Calculating MA deviation...")
    ma200_sp500  = calc_ma_deviation(sp500_vals, 200)
    ma50_sp500   = calc_ma_deviation(sp500_vals, 50)
    ma200_nasdaq = calc_ma_deviation(nasdaq_vals, 200)
    print(f"  SP500 vs 200MA={ma200_sp500}%, vs 50MA={ma50_sp500}%")
    print(f"  NASDAQ vs 200MA={ma200_nasdaq}%")

    # ── FRED 금리/신용 지표 ────────────────────────────────────────────
    print("  Fetching FRED indicators...")
    fed_rate  = fred_latest("FEDFUNDS")
    hy_spread = fred_latest("BAMLH0A0HYM2")
    ig_spread = fred_latest("BAMLC0A0CM")       # IG 스프레드 (신규)
    ted_spread= fred_latest("TEDRATE")           # TED 스프레드 (신규)
    t2y       = fred_latest("DGS2")
    t10y      = fred_latest("DGS10")
    yield_curve = round(t10y - t2y, 3) if t10y and t2y else None

    # ── 경기 실물 지표 ─────────────────────────────────────────────────
    print("  Fetching macro indicators...")
    jobless_claims = fred_latest("ICSA")         # 실업수당 청구 (신규)
    fed_assets     = fred_latest("WALCL")        # Fed 자산 규모 (신규, 단위: 백만달러)

    print(f"  IG={ig_spread}, TED={ted_spread}, Jobless={jobless_claims}, FedAssets={fed_assets}")

    # ── Fear & Greed ───────────────────────────────────────────────────
    print("  Fetching Fear & Greed...")
    fg   = fear_greed_latest()
    fg_h = fear_greed_history(45)

    # ── 35일 히스토리 (차트용) ─────────────────────────────────────────
    print("  Fetching 35-day history for charts...")
    tnx_h = fred_history("DGS10",        45)
    hy_h  = fred_history("BAMLH0A0HYM2", 45)
    ig_h  = fred_history("BAMLC0A0CM",   45)
    t2_h  = fred_history("DGS2",         45)
    t10_h = fred_history("DGS10",        45)
    t2_map = {d["date"]: d["value"] for d in t2_h}
    yc_h   = [{"date": d["date"], "value": round(d["value"] - t2_map[d["date"]], 3)}
               for d in t10_h if d["date"] in t2_map]

    # 차트용 35일만 슬라이싱
    nasdaq_chart = nasdaq_h[-35:] if len(nasdaq_h) >= 35 else nasdaq_h
    sp500_chart  = sp500_h[-35:]  if len(sp500_h)  >= 35 else sp500_h
    djia_chart   = djia_h[-35:]   if len(djia_h)   >= 35 else djia_h

    # ── 리스크 점수 (위험 경보) ────────────────────────────────────────
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

    # ── 매수 타이밍 점수 (반등 조건) ──────────────────────────────────
    buy_score = 0
    buy_signals = []

    # RSI 과매도
    if rsi_sp500 is not None:
        if rsi_sp500 < 25:
            buy_score += 25
            buy_signals.append({"label": f"S&P500 RSI {rsi_sp500} — 극단 과매도 (강한 반등 후보)", "strength": "strong"})
        elif rsi_sp500 < 30:
            buy_score += 18
            buy_signals.append({"label": f"S&P500 RSI {rsi_sp500} — 과매도 구간", "strength": "medium"})
        elif rsi_sp500 < 40:
            buy_score += 8
            buy_signals.append({"label": f"S&P500 RSI {rsi_sp500} — 약한 과매도", "strength": "weak"})

    if rsi_nasdaq is not None and rsi_nasdaq < 30:
        buy_score += 10
        buy_signals.append({"label": f"NASDAQ RSI {rsi_nasdaq} — 기술주 과매도", "strength": "medium"})

    # 200일 이평선 괴리율
    if ma200_sp500 is not None:
        if ma200_sp500 < -20:
            buy_score += 25
            buy_signals.append({"label": f"S&P500, 200일선 대비 {ma200_sp500}% — 역사적 저평가", "strength": "strong"})
        elif ma200_sp500 < -15:
            buy_score += 18
            buy_signals.append({"label": f"S&P500, 200일선 대비 {ma200_sp500}% — 강한 매수 구간", "strength": "strong"})
        elif ma200_sp500 < -10:
            buy_score += 10
            buy_signals.append({"label": f"S&P500, 200일선 대비 {ma200_sp500}% — 매수 후보 구간", "strength": "medium"})

    # Fear & Greed 극단 공포
    if fg and fg["value"] < 15:
        buy_score += 20
        buy_signals.append({"label": f"Fear&Greed {fg['value']} — 극단 공포 (역발상 매수)", "strength": "strong"})
    elif fg and fg["value"] < 25:
        buy_score += 12
        buy_signals.append({"label": f"Fear&Greed {fg['value']} — Extreme Fear 구간", "strength": "medium"})

    # VIX 스파이크 (급등 후 안정화 조짐)
    if vix and vix > 35:
        buy_score += 10
        buy_signals.append({"label": f"VIX {vix} — 공포 극점 근처 (역발상 기회)", "strength": "medium"})

    # HY스프레드 (극단 확대는 오히려 바닥 신호)
    if hy_spread and hy_spread > 8:
        buy_score += 10
        buy_signals.append({"label": f"HY스프레드 {hy_spread}% — 신용 공포 극점 (바닥 후보)", "strength": "medium"})

    # IG 스프레드 안정 (HY보다 먼저 안정되면 반등 선행)
    if ig_spread and hy_spread and ig_spread < hy_spread * 0.25:
        buy_score += 8
        buy_signals.append({"label": f"IG스프레드 {ig_spread}% — 우량채 먼저 안정화 (반등 선행 신호)", "strength": "medium"})

    buy_score = min(buy_score, 100)

    # 종합 판단
    if risk >= 50 and buy_score >= 60:
        trade_signal = "매수 타이밍"
        trade_color  = "green"
        trade_desc   = "하락 확인 + 반등 조건 다수 충족 — 분할 매수 적극 검토"
    elif risk >= 50 and buy_score >= 35:
        trade_signal = "분할 매수 준비"
        trade_color  = "amber"
        trade_desc   = "하락 확인 + 반등 조건 일부 충족 — 소량 선취매 고려"
    elif risk >= 50 and buy_score < 35:
        trade_signal = "관망"
        trade_color  = "red"
        trade_desc   = "하락 중이나 반등 조건 미충족 — 추가 하락 가능성"
    elif risk < 30:
        trade_signal = "중립"
        trade_color  = "blue"
        trade_desc   = "시장 안정 — 급락 매수 기회 아님"
    else:
        trade_signal = "주의 관찰"
        trade_color  = "amber"
        trade_desc   = "불확실 구간 — 지표 추이 모니터링"

    print(f"  Risk={risk}, BuyScore={buy_score}, Signal={trade_signal}")

    output = {
        "updated_at": today,
        "updated_kst": (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST"),
        "snapshot": {
            "nasdaq": nasdaq, "sp500": sp500, "djia": djia, "vix": vix,
            "ten_yr": t10y, "fed_rate": fed_rate, "hy_spread": hy_spread,
            "ig_spread": ig_spread, "ted_spread": ted_spread,
            "yield_curve": yield_curve, "fear_greed": fg,
            "put_call": None,
            "jobless_claims": jobless_claims,
            "fed_assets": fed_assets,
        },
        "technicals": {
            "rsi_sp500":    rsi_sp500,
            "rsi_nasdaq":   rsi_nasdaq,
            "ma200_sp500":  ma200_sp500,
            "ma50_sp500":   ma50_sp500,
            "ma200_nasdaq": ma200_nasdaq,
        },
        "risk_score":   risk,
        "risk_label":   risk_label,
        "buy_score":    buy_score,
        "buy_signals":  buy_signals,
        "trade_signal": trade_signal,
        "trade_color":  trade_color,
        "trade_desc":   trade_desc,
        "history": {
            "nasdaq":      nasdaq_chart,
            "sp500":       sp500_chart,
            "djia":        djia_chart,
            "vix":         vix_h,
            "tnx":         tnx_h,
            "hy_spread":   hy_h,
            "ig_spread":   ig_h,
            "yield_curve": yc_h,
            "fear_greed":  fg_h,
        },
    }

    os.makedirs("data", exist_ok=True)
    with open("data/indicators.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  Done. Risk={risk}/100, BuyScore={buy_score}/100, Signal={trade_signal}")

if __name__ == "__main__":
    main()
