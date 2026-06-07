import json
import os
from datetime import datetime, timedelta
import requests

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_BASE    = "https://api.stlouisfed.org/fred/series/observations"
FMP_API_KEY  = os.environ.get("FMP_API_KEY", "")
FMP_BASE     = "https://financialmodelingprep.com/api/v3"

WATCHLIST = [
    {"ticker": "SOXL",  "name": "반도체 3x 레버리지"},
    {"ticker": "TQQQ",  "name": "나스닥 3x 레버리지"},
    {"ticker": "XLK",   "name": "기술 섹터"},
    {"ticker": "XLV",   "name": "헬스케어/바이오"},
    {"ticker": "XLE",   "name": "정유/에너지"},
    {"ticker": "XLF",   "name": "금융 섹터"},
    {"ticker": "XLI",   "name": "산업/항공"},
    {"ticker": "XLU",   "name": "유틸리티 (방어주)"},
    {"ticker": "XLY",   "name": "소비재"},
    {"ticker": "GLD",   "name": "금 (Gold)"},
    {"ticker": "TLT",   "name": "장기국채 20년+"},
    {"ticker": "ARKK",  "name": "혁신/테크 액티브"},
]
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

def calc_ma(values, period):
    """단순 이동평균"""
    if len(values) < period:
        return None
    return round(sum(values[-period:]) / period, 4)

def calc_ma_slope(values, period, lookback=5):
    """이평선 기울기 — 최근 N일간 방향 (+상승/-하락)"""
    if len(values) < period + lookback:
        return None
    ma_now  = sum(values[-(period):])   / period
    ma_prev = sum(values[-(period+lookback):-lookback]) / period
    return round((ma_now - ma_prev) / ma_prev * 100, 3)

def calc_vs_ma(current, ma_val):
    """현재값이 이평선 대비 몇 % 위/아래인지"""
    if current is None or ma_val is None or ma_val == 0:
        return None
    return round((current - ma_val) / ma_val * 100, 2)

def rate_direction(history, lookback_days=90):
    """N일 전 대비 방향과 변화폭 반환"""
    if not history or len(history) < 5:
        return None, None
    current = history[-1]["value"]
    # lookback_days 전 근처 값 찾기
    target_date = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    past_val = None
    for d in history:
        if d["date"] >= target_date:
            past_val = d["value"]
            break
    if past_val is None:
        past_val = history[0]["value"]
    change = round(current - past_val, 3)
    return current, change

def calc_ma_deviation(values, period=200):
    """현재가 대비 N일 이동평균 괴리율 (%)"""
    if len(values) < period:
        return None
    ma = sum(values[-period:]) / period
    current = values[-1]
    return round((current - ma) / ma * 100, 2)

def calc_ma_deviation_50(values):
    return calc_ma_deviation(values, 50)

def calc_rsi_list(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = 0, 0
    for i in range(len(closes) - period, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0: gains  += diff
        else:        losses -= diff
    avg_gain = gains  / period
    avg_loss = losses / period
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)

def fetch_stock_technicals(ticker):
    """FMP에서 종목 기술적 지표 수집 및 계산"""
    if not FMP_API_KEY:
        return None
    try:
        url = f"{FMP_BASE}/historical-price-full/{ticker}?timeseries=220&apikey={FMP_API_KEY}"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        hist = data.get("historical", [])
        if not hist:
            return None
        hist = list(reversed(hist))  # 오래된 순
        closes  = [d["close"]  for d in hist]
        volumes = [d["volume"] for d in hist]
        current = closes[-1]
        prev    = closes[-2] if len(closes) > 1 else current

        # RSI
        rsi = calc_rsi_list(closes, 14)

        # 이동평균
        ma50  = round(sum(closes[-50:])/50,   2) if len(closes) >= 50  else None
        ma200 = round(sum(closes[-200:])/200, 2) if len(closes) >= 200 else None
        ma20  = round(sum(closes[-20:])/20,   2) if len(closes) >= 20  else None
        ma20_5ago = round(sum(closes[-25:-5])/20, 2) if len(closes) >= 25 else None

        vs_ma50   = round((current - ma50)  / ma50  * 100, 2) if ma50  else None
        vs_ma200  = round((current - ma200) / ma200 * 100, 2) if ma200 else None
        ma20_slope= round((ma20 - ma20_5ago) / ma20_5ago * 100, 2) if (ma20 and ma20_5ago) else None

        # 볼린저밴드
        bb_pos = None
        if len(closes) >= 20:
            sl   = closes[-20:]
            mean = sum(sl) / 20
            std  = (sum((v - mean)**2 for v in sl) / 20) ** 0.5
            bb_upper = mean + 2 * std
            bb_lower = mean - 2 * std
            if bb_upper != bb_lower:
                bb_pos = round((current - bb_lower) / (bb_upper - bb_lower) * 100, 1)

        # 52주
        w52      = closes[-252:] if len(closes) >= 252 else closes
        high52   = max(w52)
        low52    = min(w52)
        vs_high52= round((current - high52) / high52 * 100, 2)
        vs_low52 = round((current - low52)  / low52  * 100, 2)

        # 거래량
        vol20avg = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else None
        vol_ratio= round(volumes[-1] / vol20avg * 100, 1) if vol20avg else None

        # 매수 점수
        buy_score, buy_signals = 0, []
        if rsi is not None:
            if rsi < 25:   buy_score += 25; buy_signals.append(f"RSI {rsi} — 극단 과매도")
            elif rsi < 30: buy_score += 18; buy_signals.append(f"RSI {rsi} — 과매도")
            elif rsi < 40: buy_score += 8;  buy_signals.append(f"RSI {rsi} — 약한 과매도")
        if vs_ma200 is not None:
            if vs_ma200 < -20:   buy_score += 25; buy_signals.append(f"200일선 {vs_ma200}% — 역사적 저평가")
            elif vs_ma200 < -15: buy_score += 18; buy_signals.append(f"200일선 {vs_ma200}% — 강한 매수")
            elif vs_ma200 < -10: buy_score += 10; buy_signals.append(f"200일선 {vs_ma200}% — 매수 후보")
        if bb_pos is not None and bb_pos < 15:
            buy_score += 15; buy_signals.append(f"볼린저 하단 ({bb_pos}%) — 반등 후보")
        if vs_high52 < -30:
            buy_score += 10; buy_signals.append(f"52주 고점 대비 {vs_high52}%")

        # 매도 점수
        sell_score, sell_signals = 0, []
        if rsi is not None:
            if rsi > 80:   sell_score += 25; sell_signals.append(f"RSI {rsi} — 극단 과매수")
            elif rsi > 70: sell_score += 18; sell_signals.append(f"RSI {rsi} — 과매수")
            elif rsi > 65: sell_score += 8;  sell_signals.append(f"RSI {rsi} — 과열 주의")
        if vs_ma200 is not None:
            if vs_ma200 > 25:   sell_score += 25; sell_signals.append(f"200일선 +{vs_ma200}% — 역사적 고평가")
            elif vs_ma200 > 20: sell_score += 18; sell_signals.append(f"200일선 +{vs_ma200}% — 강한 매도")
            elif vs_ma200 > 15: sell_score += 10; sell_signals.append(f"200일선 +{vs_ma200}% — 과열 주의")
        if bb_pos is not None and bb_pos > 85:
            sell_score += 15; sell_signals.append(f"볼린저 상단 ({bb_pos}%) — 조정 후보")
        if vs_low52 > 80:
            sell_score += 10; sell_signals.append(f"52주 저점 대비 +{vs_low52}%")
        if vol_ratio and vol_ratio > 200 and rsi and rsi > 65:
            sell_score += 8; sell_signals.append(f"고점 거래량 급증 ({vol_ratio}%)")

        buy_score  = min(buy_score,  100)
        sell_score = min(sell_score, 100)

        chg1d = round((current - prev) / prev * 100, 2)

        return {
            "ticker":       ticker,
            "price":        round(current, 2),
            "chg1d":        chg1d,
            "rsi":          rsi,
            "vs_ma50":      vs_ma50,
            "vs_ma200":     vs_ma200,
            "ma20_slope":   ma20_slope,
            "bb_pos":       bb_pos,
            "vs_high52":    vs_high52,
            "vs_low52":     vs_low52,
            "vol_ratio":    vol_ratio,
            "high52":       round(high52, 2),
            "low52":        round(low52,  2),
            "ma200":        ma200,
            "buy_score":    buy_score,
            "sell_score":   sell_score,
            "buy_signals":  buy_signals,
            "sell_signals": sell_signals,
        }
    except Exception as e:
        print(f"  [ERROR] {ticker}: {e}")
        return None

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

    # ── 종목 기술적 분석 (워치리스트) ─────────────────────────────────
    print("  Fetching watchlist technicals...")
    watchlist_data = []
    for item in WATCHLIST:
        print(f"    {item['ticker']}...", end=" ")
        result = fetch_stock_technicals(item["ticker"])
        if result:
            result["name"] = item["name"]
            watchlist_data.append(result)
            print(f"buy={result['buy_score']} sell={result['sell_score']}")
        else:
            print("failed")
    
    # ── 환율 (USD/KRW) ────────────────────────────────────────────────
    print("  Fetching USD/KRW rate...")
    usdkrw = fred_latest("DEXKOUS")   # FRED: 원/달러 환율
    print(f"  USD/KRW={usdkrw}")
    
    # ── 금리 방향 분석 (3개월 전 대비) ───────────────────────────────
    print("  Calculating rate direction...")
    t10y_hist_long = fred_history("DGS10",    120)
    fedfunds_hist  = fred_history("FEDFUNDS", 120)

    _, t10y_change_3m    = rate_direction(t10y_hist_long,   90)
    _, fedfunds_change_3m= rate_direction(fedfunds_hist,    90)
    _, t10y_change_1m    = rate_direction(t10y_hist_long,   30)

    # 실질금리 근사 (10년물 - 기대인플레 2.3% 고정 근사)
    real_rate = round(t10y - 2.3, 2) if t10y else None

    # 주식 이익수익률 vs 10년물 (ERP 근사)
    # S&P500 PER 약 22배 가정 → E/P = 4.5%
    sp500_earnings_yield = round(100 / 22, 2)  # 간단 근사
    erp = round(sp500_earnings_yield - t10y, 2) if t10y else None

    print(f"  T10Y 3M change={t10y_change_3m}, 1M={t10y_change_1m}")
    print(f"  Fed 3M change={fedfunds_change_3m}")
    print(f"  RealRate={real_rate}%, ERP={erp}%")
    
    # ── 이평선 분석 ────────────────────────────────────────────────────
    print("  Calculating moving average analysis...")

    # VIX 이평선
    vix_vals    = [d["value"] for d in vix_h]
    vix_ma20    = calc_ma(vix_vals, 20)
    vix_vs_ma20 = calc_vs_ma(vix, vix_ma20)
    vix_slope   = calc_ma_slope(vix_vals, 20)

    # HY 스프레드 이평선
    hy_hist     = fred_history("BAMLH0A0HYM2", 60)
    hy_vals     = [d["value"] for d in hy_hist]
    hy_ma20     = calc_ma(hy_vals, 20)
    hy_vs_ma20  = calc_vs_ma(hy_spread, hy_ma20)
    hy_slope    = calc_ma_slope(hy_vals, 20)

    # Fear & Greed 10일 이평선
    fg_vals     = [d["value"] for d in fg_h]
    fg_ma10     = calc_ma(fg_vals, 10)
    fg_vs_ma10  = calc_vs_ma(fg["value"] if fg else None, fg_ma10)
    fg_slope    = calc_ma_slope(fg_vals, 10)

    print(f"  VIX vs MA20={vix_vs_ma20}%, slope={vix_slope}%")
    print(f"  HY  vs MA20={hy_vs_ma20}%, slope={hy_slope}%")
    print(f"  F&G vs MA10={fg_vs_ma10}%, slope={fg_slope}%")

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
    
    # VIX 이평선 매수 신호
    if vix_vs_ma20 is not None:
        if vix_vs_ma20 > 80:
            buy_score += 20
            buy_signals.append({"label": f"VIX, 20일선 대비 +{vix_vs_ma20}% — 공포 극점 (강한 역발상 매수)", "strength": "strong"})
        elif vix_vs_ma20 > 50:
            buy_score += 12
            buy_signals.append({"label": f"VIX, 20일선 대비 +{vix_vs_ma20}% — 공포 급증 구간", "strength": "medium"})

    # VIX 이평선 하락 전환 (안정화 신호)
    if vix_slope is not None and vix_slope < -5 and vix_vs_ma20 and vix_vs_ma20 > 20:
        buy_score += 15
        buy_signals.append({"label": f"VIX 20일선 기울기 {vix_slope}% — 하락 전환 (공포 완화, 반등 선행)", "strength": "strong"})

    # HY 이평선 매수 신호 (고점 이탈 후 하락)
    if hy_slope is not None and hy_slope < -3:
        buy_score += 12
        buy_signals.append({"label": f"HY스프레드 20일선 기울기 {hy_slope}% — 하락 전환 (신용 안정화)", "strength": "medium"})

    # F&G 이평선 매수 신호
    if fg_slope is not None and fg_slope < -8 and fg_ma10 and fg_ma10 < 35:
        buy_score += 10
        buy_signals.append({"label": f"Fear&Greed 10일 이평 {round(fg_ma10,1)} — 공포 추세 (역발상 구간)", "strength": "medium"})
    buy_score = min(buy_score, 100)
   
    # ── 매도 타이밍 점수 (과열 조건) ──────────────────────────────────
    sell_score = 0
    sell_signals = []

    # RSI 과매수
    if rsi_sp500 is not None:
        if rsi_sp500 > 80:
            sell_score += 25
            sell_signals.append({"label": f"S&P500 RSI {rsi_sp500} — 극단 과매수 (강한 매도 신호)", "strength": "strong"})
        elif rsi_sp500 > 70:
            sell_score += 18
            sell_signals.append({"label": f"S&P500 RSI {rsi_sp500} — 과매수 구간", "strength": "medium"})
        elif rsi_sp500 > 65:
            sell_score += 8
            sell_signals.append({"label": f"S&P500 RSI {rsi_sp500} — 과열 주의", "strength": "weak"})

    if rsi_nasdaq is not None and rsi_nasdaq > 70:
        sell_score += 10
        sell_signals.append({"label": f"NASDAQ RSI {rsi_nasdaq} — 기술주 과매수", "strength": "medium"})

    # 200일 이평선 괴리율 (고평가)
    if ma200_sp500 is not None:
        if ma200_sp500 > 25:
            sell_score += 25
            sell_signals.append({"label": f"S&P500, 200일선 대비 +{ma200_sp500}% — 역사적 고평가", "strength": "strong"})
        elif ma200_sp500 > 20:
            sell_score += 18
            sell_signals.append({"label": f"S&P500, 200일선 대비 +{ma200_sp500}% — 강한 매도 구간", "strength": "strong"})
        elif ma200_sp500 > 15:
            sell_score += 10
            sell_signals.append({"label": f"S&P500, 200일선 대비 +{ma200_sp500}% — 과열 주의 구간", "strength": "medium"})

    # Fear & Greed 극단 탐욕
    if fg and fg["value"] > 85:
        sell_score += 20
        sell_signals.append({"label": f"Fear&Greed {fg['value']} — 극단 탐욕 (역발상 매도)", "strength": "strong"})
    elif fg and fg["value"] > 75:
        sell_score += 12
        sell_signals.append({"label": f"Fear&Greed {fg['value']} — Extreme Greed 구간", "strength": "medium"})

    # VIX 극단 저점 (방심 극점 = 위험)
    if vix and vix < 12:
        sell_score += 20
        sell_signals.append({"label": f"VIX {vix} — 역대 최저 수준 방심 (급등 리스크)", "strength": "strong"})
    elif vix and vix < 15:
        sell_score += 10
        sell_signals.append({"label": f"VIX {vix} — 낮은 변동성 구간 (조정 전 경계)", "strength": "medium"})

    # HY 스프레드 극단 축소 (리스크 완전 무시)
    if hy_spread and hy_spread < 3.0:
        sell_score += 15
        sell_signals.append({"label": f"HY스프레드 {hy_spread}% — 리스크 프리미엄 소멸 (과열)", "strength": "strong"})
    elif hy_spread and hy_spread < 3.5:
        sell_score += 8
        sell_signals.append({"label": f"HY스프레드 {hy_spread}% — 과도한 낙관 구간", "strength": "medium"})

    # 수익률 곡선 급격한 정상화 (침체 시작 신호)
    if yield_curve is not None and yield_curve > 0.8:
        sell_score += 10
        sell_signals.append({"label": f"수익률곡선 {yield_curve}% — 역전 후 급속 정상화 (침체 진입 가능)", "strength": "medium"})
    
    # VIX 이평선 매도 신호 (20일선 대비 극단 저점 = 방심)
    if vix_vs_ma20 is not None and vix_vs_ma20 < -25:
        sell_score += 15
        sell_signals.append({"label": f"VIX, 20일선 대비 {vix_vs_ma20}% — 변동성 극단 억제 (방심 극점)", "strength": "medium"})

    # VIX 이평선 상승 전환 (불안 증가 = 포지션 축소 신호)
    if vix_slope is not None and vix_slope > 10 and vix_ma20 and vix_ma20 < 20:
        sell_score += 12
        sell_signals.append({"label": f"VIX 20일선 기울기 +{vix_slope}% — 저VIX에서 상승 전환 (경계)", "strength": "medium"})

    # HY 이평선 매도 신호 (극단 축소 + 상승 전환)
    if hy_slope is not None and hy_slope > 5 and hy_ma20 and hy_ma20 < 3.5:
        sell_score += 12
        sell_signals.append({"label": f"HY스프레드 20일선 기울기 +{hy_slope}% — 극저점에서 반등 (위험)", "strength": "medium"})

    # F&G 이평선 매도 신호
    if fg_slope is not None and fg_slope > 8 and fg_ma10 and fg_ma10 > 65:
        sell_score += 10
        sell_signals.append({"label": f"Fear&Greed 10일 이평 {round(fg_ma10,1)} — 탐욕 추세 가속", "strength": "medium"})
    
    sell_score = min(sell_score, 100)

    # 매도 종합 판단
    if sell_score >= 65:
        sell_signal = "매도 타이밍"
        sell_color  = "red"
        sell_desc   = "과열 지표 다수 충족 — 비중 축소 또는 익절 적극 검토"
    elif sell_score >= 40:
        sell_signal = "부분 익절 검토"
        sell_color  = "amber"
        sell_desc   = "과열 신호 일부 감지 — 고점 리스크 인식, 분할 익절 고려"
    elif sell_score >= 20:
        sell_signal = "주의 관찰"
        sell_color  = "amber"
        sell_desc   = "일부 과열 조짐 — 추가 매수보다 보유 관리 집중"
    else:
        sell_signal = "홀딩"
        sell_color  = "blue"
        sell_desc   = "과열 신호 없음 — 현 포지션 유지"

    print(f"  SellScore={sell_score}, SellSignal={sell_signal}")
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
            "usdkrw":             usdkrw,
            "t10y_change_3m":     t10y_change_3m,
            "t10y_change_1m":     t10y_change_1m,
            "fedfunds_change_3m": fedfunds_change_3m,
            "real_rate":          real_rate,
            "erp":                erp,
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
            "vix_ma20":     vix_ma20,
            "vix_vs_ma20":  vix_vs_ma20,
            "vix_slope":    vix_slope,
            "hy_ma20":      hy_ma20,
            "hy_vs_ma20":   hy_vs_ma20,
            "hy_slope":     hy_slope,
            "fg_ma10":      round(fg_ma10, 1) if fg_ma10 else None,
            "fg_vs_ma10":   fg_vs_ma10,
            "fg_slope":     fg_slope,
        },
        "risk_score":   risk,
        "risk_label":   risk_label,
        "buy_score":    buy_score,
        "buy_signals":  buy_signals,
        "trade_signal": trade_signal,
        "trade_color":  trade_color,
        "trade_desc":   trade_desc,
        "sell_score":   sell_score,
        "sell_signals": sell_signals,
        "sell_signal":  sell_signal,
        "sell_color":   sell_color,
        "sell_desc":    sell_desc,
        "watchlist": watchlist_data,
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
