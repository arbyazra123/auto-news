#!/usr/bin/env python3
"""
Equity signal engine: per-ticker composite scoring -> BUY / HOLD / SELL.

Deterministic, rules-based composite (0-100) built from five components:
- trend          (30%): close vs SMA20/50/200 + SMA50 slope
- momentum       (25%): 1M and 3M returns
- mean_reversion (15%): RSI(14) regime
- volume_flow    (20%): MFI(14) + OBV slope (smart-money proxy)
- macd           (10%): histogram sign and direction

Signal mapping: score >= 65 BUY, score <= 40 SELL, otherwise HOLD.
News mentions are attached as context for the Claude overlay; they do not
move the deterministic score.
"""
import logging
import re
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volume import MFIIndicator, OnBalanceVolumeIndicator

logger = logging.getLogger("idx-stock-api")

SIGNAL_WEIGHTS = {
    "trend": 0.30,
    "momentum": 0.25,
    "mean_reversion": 0.15,
    "volume_flow": 0.20,
    "macd": 0.10,
}

BUY_THRESHOLD = 65
SELL_THRESHOLD = 40

MIN_HISTORY_BARS = 60  # minimum daily bars to score a ticker


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _slope(series: pd.Series, lookback: int = 10) -> float:
    """Simple slope (last - first) / abs(first) over a window; robust to const."""
    series = series.dropna()
    if len(series) < lookback:
        return 0.0
    a, b = float(series.iloc[-lookback]), float(series.iloc[-1])
    denom = abs(a) if abs(a) > 1e-9 else 1.0
    return (b - a) / denom


def ensure_idx_ticker(symbol: str) -> str:
    """Ensure ticker has .JK suffix for Indonesian stocks"""
    symbol = symbol.upper().strip()
    if not symbol.endswith(".JK"):
        symbol = f"{symbol}.JK"
    return symbol


# ============================================================================
# COMPONENT SCORES (each 0-100, 50 = neutral)
# ============================================================================

def _trend_score(close: pd.Series) -> tuple:
    price = float(close.iloc[-1])
    sma20 = SMAIndicator(close=close, window=20).sma_indicator()
    sma50 = SMAIndicator(close=close, window=50).sma_indicator()
    sma200 = SMAIndicator(close=close, window=200).sma_indicator() if len(close) >= 200 else None

    score = 50.0
    notes = []

    if not pd.isna(sma20.iloc[-1]):
        above = price > float(sma20.iloc[-1])
        score += 12.5 if above else -12.5
        notes.append("above SMA20" if above else "below SMA20")
    if not pd.isna(sma50.iloc[-1]):
        above = price > float(sma50.iloc[-1])
        score += 12.5 if above else -12.5
        notes.append("above SMA50" if above else "below SMA50")
        slope50 = _slope(sma50, 10)
        score += 10 if slope50 > 0 else -10
        notes.append("SMA50 rising" if slope50 > 0 else "SMA50 falling")
    if sma200 is not None and not pd.isna(sma200.iloc[-1]):
        above = price > float(sma200.iloc[-1])
        score += 15 if above else -15
        notes.append("above SMA200" if above else "below SMA200")

    return _clamp(score), notes


def _momentum_score(close: pd.Series) -> tuple:
    score = 50.0
    notes = []

    if len(close) >= 22:
        ret_1m = float(close.iloc[-1]) / float(close.iloc[-22]) - 1.0
        score += _clamp(ret_1m * 250, -25, 25)
        notes.append(f"1M return {ret_1m * 100:+.1f}%")
    if len(close) >= 64:
        ret_3m = float(close.iloc[-1]) / float(close.iloc[-64]) - 1.0
        score += _clamp(ret_3m * 150, -25, 25)
        notes.append(f"3M return {ret_3m * 100:+.1f}%")

    return _clamp(score), notes


def _mean_reversion_score(close: pd.Series) -> tuple:
    rsi_series = RSIIndicator(close=close, window=14).rsi()
    rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0

    # Oversold = opportunity, overbought = risk
    if rsi < 30:
        score = 80.0
        note = f"RSI {rsi:.0f} oversold"
    elif rsi < 45:
        score = 62.0
        note = f"RSI {rsi:.0f} below neutral"
    elif rsi <= 65:
        score = 50.0
        note = f"RSI {rsi:.0f} neutral"
    elif rsi <= 75:
        score = 35.0
        note = f"RSI {rsi:.0f} overbought"
    else:
        score = 20.0
        note = f"RSI {rsi:.0f} extremely overbought"

    return score, [note], rsi


def _volume_flow_score(df: pd.DataFrame) -> tuple:
    notes = []
    score = 50.0

    try:
        mfi_series = MFIIndicator(
            high=df["High"], low=df["Low"], close=df["Close"], volume=df["Volume"], window=14
        ).money_flow_index()
        mfi = float(mfi_series.iloc[-1]) if not pd.isna(mfi_series.iloc[-1]) else 50.0
        score += _clamp((mfi - 50) * 0.6, -25, 25)
        notes.append(f"MFI {mfi:.0f}")

        obv = OnBalanceVolumeIndicator(close=df["Close"], volume=df["Volume"]).on_balance_volume()
        obv_slope = _slope(obv, 10)
        score += _clamp(obv_slope * 200, -25, 25)
        notes.append("OBV rising" if obv_slope > 0 else "OBV falling")
    except Exception as e:
        logger.warning(f"Volume flow calculation failed: {e}")
        notes.append("volume flow unavailable")

    return _clamp(score), notes


def _macd_score(close: pd.Series) -> tuple:
    macd = MACD(close=close)
    hist = macd.macd_diff()
    if len(hist.dropna()) < 2:
        return 50.0, ["MACD unavailable"]

    latest = float(hist.iloc[-1])
    prev = float(hist.iloc[-2])
    rising = latest > prev

    if latest > 0 and rising:
        return 75.0, ["MACD positive and rising"]
    if latest > 0:
        return 60.0, ["MACD positive but fading"]
    if rising:
        return 45.0, ["MACD negative but improving"]
    return 25.0, ["MACD negative and falling"]


# ============================================================================
# PER-TICKER SIGNAL
# ============================================================================

def compute_equity_signal(ticker: str, hist: pd.DataFrame, news_mentions: int = 0) -> dict:
    """Compute the composite signal for one ticker from its OHLCV history"""
    base = ticker.replace(".JK", "")

    if hist is None or hist.empty or len(hist.dropna(subset=["Close"])) < MIN_HISTORY_BARS:
        return {
            "ticker": base,
            "signal": "NO_DATA",
            "score": None,
            "close": None,
            "components": {},
            "rationale": ["Insufficient price history"],
            "news_mentions": news_mentions,
        }

    df = hist.dropna(subset=["Close"]).copy()
    close = df["Close"]

    trend, trend_notes = _trend_score(close)
    momentum, mom_notes = _momentum_score(close)
    mean_rev, rsi_notes, rsi = _mean_reversion_score(close)
    volume_flow, vol_notes = _volume_flow_score(df)
    macd, macd_notes = _macd_score(close)

    components = {
        "trend": round(trend, 1),
        "momentum": round(momentum, 1),
        "mean_reversion": round(mean_rev, 1),
        "volume_flow": round(volume_flow, 1),
        "macd": round(macd, 1),
    }

    score = sum(components[name] * weight for name, weight in SIGNAL_WEIGHTS.items())

    if score >= BUY_THRESHOLD:
        signal = "BUY"
    elif score <= SELL_THRESHOLD:
        signal = "SELL"
    else:
        signal = "HOLD"

    price = float(close.iloc[-1])
    change_1d = (price / float(close.iloc[-2]) - 1.0) * 100 if len(close) >= 2 else 0.0

    return {
        "ticker": base,
        "signal": signal,
        "score": round(score, 1),
        "close": price,
        "change_1d_pct": round(change_1d, 2),
        "rsi": round(rsi, 1),
        "components": components,
        "rationale": trend_notes + mom_notes + rsi_notes + vol_notes + macd_notes,
        "news_mentions": news_mentions,
    }


# ============================================================================
# BATCH SIGNAL GENERATION
# ============================================================================

def count_news_mentions(tickers: List[str], news_text: Optional[str]) -> Dict[str, int]:
    """Count whole-word ticker mentions in the condensed news text"""
    mentions = {t: 0 for t in tickers}
    if not news_text:
        return mentions
    for ticker in tickers:
        mentions[ticker] = len(re.findall(rf"\b{re.escape(ticker)}\b", news_text))
    return mentions


def generate_equity_signals(
    tickers: List[str],
    period: str = "1y",
    news_text: Optional[str] = None,
) -> List[dict]:
    """
    Batch-download OHLCV for the universe and score every ticker.
    Returns a list of signal dicts sorted by score (best first).
    """
    yf_tickers = [ensure_idx_ticker(t) for t in tickers]
    logger.info(f"Downloading OHLCV for {len(yf_tickers)} tickers (period={period})")

    data = yf.download(
        tickers=yf_tickers,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    mentions = count_news_mentions([t.replace(".JK", "") for t in tickers], news_text)

    signals = []
    for yf_ticker in yf_tickers:
        base = yf_ticker.replace(".JK", "")
        try:
            if len(yf_tickers) == 1:
                hist = data
            else:
                hist = data[yf_ticker] if yf_ticker in data.columns.get_level_values(0) else None
            signals.append(compute_equity_signal(yf_ticker, hist, mentions.get(base, 0)))
        except Exception as e:
            logger.error(f"Signal computation failed for {yf_ticker}: {e}")
            signals.append({
                "ticker": base,
                "signal": "ERROR",
                "score": None,
                "close": None,
                "components": {},
                "rationale": [f"Error: {e}"],
                "news_mentions": mentions.get(base, 0),
            })

    scored = [s for s in signals if s["score"] is not None]
    unscored = [s for s in signals if s["score"] is None]
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored + unscored
