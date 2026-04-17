"""
market.py — 주가/거래량/기술지표 수집 (yfinance)
"""

import yfinance as yf
import pandas as pd
import ta
import json
from datetime import datetime, timedelta


def collect(ticker: str = "NCNA") -> dict:
    stock = yf.Ticker(ticker)

    # 1년치 일봉 데이터
    hist = stock.history(period="1y")
    if hist.empty:
        raise ValueError(f"No price data for {ticker}")

    close = hist["Close"]
    volume = hist["Volume"]

    # 기술지표 계산
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    macd_obj = ta.trend.MACD(close)
    macd = macd_obj.macd()
    macd_signal = macd_obj.macd_signal()
    macd_diff = macd_obj.macd_diff()
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    sma20 = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    sma50 = ta.trend.SMAIndicator(close, window=50).sma_indicator()
    sma200 = ta.trend.SMAIndicator(close, window=200).sma_indicator()

    latest = hist.iloc[-1]
    prev = hist.iloc[-2]

    # 52주 고가/저가
    high_52w = float(close.max())
    low_52w = float(close.min())
    current_price = float(latest["Close"])

    # 가격 히스토리 (최근 252일, JSON용)
    price_history = [
        {"date": str(d.date()), "close": round(float(c), 4), "volume": int(v)}
        for d, c, v in zip(hist.index, close, volume)
    ]

    result = {
        "ticker": ticker,
        "updated_at": datetime.utcnow().isoformat(),
        "price": {
            "current": round(current_price, 4),
            "prev_close": round(float(prev["Close"]), 4),
            "change_pct": round((current_price / float(prev["Close"]) - 1) * 100, 2),
            "open": round(float(latest["Open"]), 4),
            "high": round(float(latest["High"]), 4),
            "low": round(float(latest["Low"]), 4),
            "volume": int(latest["Volume"]),
            "high_52w": round(high_52w, 4),
            "low_52w": round(low_52w, 4),
            "pct_from_52w_high": round((current_price / high_52w - 1) * 100, 2),
        },
        "technicals": {
            "rsi_14": round(float(rsi.iloc[-1]), 2) if not pd.isna(rsi.iloc[-1]) else None,
            "macd": round(float(macd.iloc[-1]), 4) if not pd.isna(macd.iloc[-1]) else None,
            "macd_signal": round(float(macd_signal.iloc[-1]), 4) if not pd.isna(macd_signal.iloc[-1]) else None,
            "macd_hist": round(float(macd_diff.iloc[-1]), 4) if not pd.isna(macd_diff.iloc[-1]) else None,
            "bb_upper": round(float(bb.bollinger_hband().iloc[-1]), 4) if not pd.isna(bb.bollinger_hband().iloc[-1]) else None,
            "bb_lower": round(float(bb.bollinger_lband().iloc[-1]), 4) if not pd.isna(bb.bollinger_lband().iloc[-1]) else None,
            "bb_mid": round(float(bb.bollinger_mavg().iloc[-1]), 4) if not pd.isna(bb.bollinger_mavg().iloc[-1]) else None,
            "sma_20": round(float(sma20.iloc[-1]), 4) if not pd.isna(sma20.iloc[-1]) else None,
            "sma_50": round(float(sma50.iloc[-1]), 4) if not pd.isna(sma50.iloc[-1]) else None,
            "sma_200": round(float(sma200.iloc[-1]), 4) if not pd.isna(sma200.iloc[-1]) else None,
        },
        "signals": _generate_signals(current_price, rsi, macd_diff, sma20, sma50, bb),
        "history": price_history,
    }

    # 시장 정보 (info)
    try:
        info = stock.info
        result["info"] = {
            "market_cap": info.get("marketCap"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
            "avg_volume_10d": info.get("averageVolume10days"),
            "short_ratio": info.get("shortRatio"),
            "short_pct_of_float": info.get("shortPercentOfFloat"),
        }
    except Exception:
        result["info"] = {}

    return result


def _generate_signals(price, rsi, macd_diff, sma20, sma50, bb) -> list:
    signals = []
    p = float(price)

    r = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
    if r < 30:
        signals.append({"type": "bullish", "indicator": "RSI", "note": f"과매도 (RSI {r:.1f})"})
    elif r > 70:
        signals.append({"type": "bearish", "indicator": "RSI", "note": f"과매수 (RSI {r:.1f})"})

    md = float(macd_diff.iloc[-1]) if not pd.isna(macd_diff.iloc[-1]) else 0
    md_prev = float(macd_diff.iloc[-2]) if not pd.isna(macd_diff.iloc[-2]) else 0
    if md > 0 and md_prev <= 0:
        signals.append({"type": "bullish", "indicator": "MACD", "note": "골든 크로스"})
    elif md < 0 and md_prev >= 0:
        signals.append({"type": "bearish", "indicator": "MACD", "note": "데드 크로스"})

    s20 = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else None
    s50 = float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else None
    if s20 and s50:
        if s20 > s50:
            signals.append({"type": "bullish", "indicator": "SMA", "note": "SMA20 > SMA50"})
        else:
            signals.append({"type": "bearish", "indicator": "SMA", "note": "SMA20 < SMA50"})

    bb_u = bb.bollinger_hband().iloc[-1]
    bb_l = bb.bollinger_lband().iloc[-1]
    if not pd.isna(bb_u) and p > float(bb_u):
        signals.append({"type": "bearish", "indicator": "BB", "note": "볼린저밴드 상단 돌파"})
    elif not pd.isna(bb_l) and p < float(bb_l):
        signals.append({"type": "bullish", "indicator": "BB", "note": "볼린저밴드 하단 이탈"})

    return signals


if __name__ == "__main__":
    data = collect("NCNA")
    print(json.dumps(data, indent=2, ensure_ascii=False))
