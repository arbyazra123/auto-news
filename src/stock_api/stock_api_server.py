#!/usr/bin/env python3
"""
Indonesian Stock Analysis REST API Server
Plain FastAPI server with all analysis functions
"""

import os
import logging
from datetime import datetime
import subprocess
import sys
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import PlainTextResponse
import uvicorn
from typing import Optional as OptionalType

# Import all dependencies
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import (
    OnBalanceVolumeIndicator,
    AccDistIndexIndicator,
    MFIIndicator,
    VolumePriceTrendIndicator
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("idx-stock-api")

# Security configuration
CLAUDE_SECRET_KEY = os.getenv("CLAUDE_SECRET_KEY", "")  # Set via env var for production
ALLOWED_IPS = ["127.0.0.1", "localhost", "::1"]  # Localhost only by default

def verify_claude_access(request: Request, x_secret_key: OptionalType[str] = Header(None)):
    """
    Security check for Claude API endpoints:
    1. Must be from localhost OR docker internal network
    2. Optional: Must provide valid secret key if CLAUDE_SECRET_KEY is set
    """
    client_ip = request.client.host

    # Check 1: IP whitelist (localhost or docker internal)
    is_local = client_ip in ALLOWED_IPS or client_ip.startswith("172.") or client_ip.startswith("192.168.")

    # Check 2: Secret key (if configured)
    if CLAUDE_SECRET_KEY:
        if not x_secret_key or x_secret_key != CLAUDE_SECRET_KEY:
            logger.warning(f"Unauthorized Claude API access attempt from {client_ip}")
            raise HTTPException(
                status_code=403,
                detail="Forbidden"
            )
    elif not is_local:
        # If no secret key configured, strictly enforce localhost only
        logger.warning(f"Unauthorized Claude API access attempt from {client_ip} (not localhost)")
        raise HTTPException(
            status_code=403,
            detail="Forbidden"
        )

    logger.info(f"Claude API access granted to {client_ip}")

# Server configuration
# HTTP_HOST = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
# HTTP_PORT = int(os.getenv("MCP_HTTP_PORT", "8000"))

# FastAPI app
app = FastAPI(
    title="Indonesian Stock Analysis API",
    description="REST API for analyzing Indonesian stocks (IDX)",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# NEWS PIPELINE - GLOBAL STATE & MODELS
# ============================================================================

pipeline_status = {
    "is_running": False,
    "last_run": None,
    "last_status": None,
    "last_error": None
}

class GetNewsRequest(BaseModel):
    max_items: int = Field(default=100, description="Max articles to scrape")
    query: str = Field(
        default="today's indonesia stock market movements, price changes, trading analysis, and financial news",
        description="Search query for semantic search"
    )
    top_k: int = Field(default=30, description="Number of top relevant articles to retrieve")
    days_back: int = Field(default=2, description="Get articles from last N days")
    max_chars: int = Field(default=2000, description="Max characters per article in output")
    output: str = Field(default="news_condensed.txt", description="Output file name")
    skip_scrape: bool = Field(default=False, description="Skip scraping, use existing news.txt")
    skip_index: bool = Field(default=False, description="Skip indexing, use existing Milvus data")

# ============================================================================
# NEWS PIPELINE - FUNCTIONS
# ============================================================================

def run_pipeline(params: GetNewsRequest):
    """Run the news pipeline in background"""
    global pipeline_status

    path = Path("data")

    try:
        pipeline_status["is_running"] = True
        pipeline_status["last_error"] = None

        logger.info("Starting news pipeline via API")

        # Clean up old files for fresh run
        files_to_remove = ["news.txt", params.output]
        for file_name in files_to_remove:
            file_path = path / file_name
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Removed old file: {file_name}")

        # Get script directory
        script_dir = Path(__file__).parent

        # Build command (news_pipeline.py is in helper/ directory)
        cmd = [
            sys.executable,
            str(script_dir / "helper" / "news_pipeline.py"),
            "--max_items", str(params.max_items),
            "--query", params.query,
            "--top_k", str(params.top_k),
            "--max_chars", str(params.max_chars),
            "--output", str(path / params.output)
        ]

        if params.days_back is not None:
            cmd.extend(["--days_back", str(params.days_back)])

        if params.skip_scrape:
            cmd.append("--skip_scrape")

        if params.skip_index:
            cmd.append("--skip_index")

        logger.info(f"Running command: {' '.join(cmd)}")

        # Run pipeline
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )

        pipeline_status["last_status"] = "success"
        pipeline_status["last_run"] = datetime.now().isoformat()
        logger.info("Pipeline completed successfully")

        return result.stdout

    except subprocess.CalledProcessError as e:
        error_msg = f"Pipeline failed: {e.stderr}"
        logger.error(error_msg)
        pipeline_status["last_status"] = "failed"
        pipeline_status["last_error"] = error_msg
        pipeline_status["last_run"] = datetime.now().isoformat()
        raise

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        pipeline_status["last_status"] = "failed"
        pipeline_status["last_error"] = error_msg
        pipeline_status["last_run"] = datetime.now().isoformat()
        raise

    finally:
        pipeline_status["is_running"] = False

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def ensure_idx_ticker(symbol: str) -> str:
    """Ensure ticker has .JK suffix for Indonesian stocks"""
    symbol = symbol.upper().strip()
    if not symbol.endswith(".JK"):
        symbol = f"{symbol}.JK"
    return symbol


def _slope(series: pd.Series, lookback: int = 10) -> float:
    """Simple slope (last - first) / abs(first) over a window; robust to const."""
    if len(series) < lookback:
        return 0.0
    a, b = float(series.iloc[-lookback]), float(series.iloc[-1])
    denom = abs(a) if abs(a) > 1e-9 else 1.0
    return (b - a) / denom


# ============================================================================
# BANDARMOLOGY (Smart-Money) LOGIC
# ============================================================================

def calculate_bandarmology(hist: pd.DataFrame) -> dict:
    """
    Bandarmology-style proxy using public Yahoo Finance OHLCV:
    - OBV / ADL / VPT trend (smart-money flow)
    - Volume spike vs 20d average
    - Money Flow Index regime/trend
    - Price compression & absorption bars
    - Breakout readiness + risk (ATR)
    Returns a 0-100 score, detected phase (Wyckoff-like), and actionable levels.
    """
    if hist.empty or len(hist) < 40:
        return {"score": 0, "phase": "INSUFFICIENT_DATA", "signals": {}, "levels": {}, "setup": {"type": "WAIT", "guidance": "Insufficient data for analysis"}, "risk": {"atr": 0, "atr_pct": 0, "suggested_stop_atr": 1.5, "suggested_tp_atr": 3.0}}

    df = hist.copy()

    # Validate data quality
    if df["Volume"].sum() == 0 or df["Close"].isna().all():
        return {"score": 0, "phase": "INVALID_DATA", "signals": {}, "levels": {}, "setup": {"type": "WAIT", "guidance": "Invalid or missing price/volume data"}, "risk": {"atr": 0, "atr_pct": 0, "suggested_stop_atr": 1.5, "suggested_tp_atr": 3.0}}

    # Indicators with error handling
    try:
        obv = OnBalanceVolumeIndicator(close=df["Close"], volume=df["Volume"]).on_balance_volume()
        adl = AccDistIndexIndicator(high=df["High"], low=df["Low"], close=df["Close"], volume=df["Volume"]).acc_dist_index()
        vpt = VolumePriceTrendIndicator(close=df["Close"], volume=df["Volume"]).volume_price_trend()
        mfi = MFIIndicator(high=df["High"], low=df["Low"], close=df["Close"], volume=df["Volume"], window=14).money_flow_index()
        atr14 = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=14).average_true_range()
    except Exception as e:
        logger.error(f"Error calculating bandarmology indicators: {e}")
        return {"score": 0, "phase": "CALCULATION_ERROR", "signals": {}, "levels": {}, "setup": {"type": "WAIT", "guidance": f"Error calculating indicators: {str(e)}"}, "risk": {"atr": 0, "atr_pct": 0, "suggested_stop_atr": 1.5, "suggested_tp_atr": 3.0}}

    # Moving averages for trend context
    ema20 = EMAIndicator(close=df["Close"], window=20).ema_indicator()
    sma50 = SMAIndicator(close=df["Close"], window=50).sma_indicator() if len(df) >= 50 else None

    # Volume stats with safeguards against division by zero
    vol_avg20 = df["Volume"].rolling(20).mean()
    # Add epsilon to avoid division by zero
    vol_avg20_safe = vol_avg20.replace(0, 1e-6)
    vol_ratio = df["Volume"] / vol_avg20_safe
    latest_vol_ratio = float(vol_ratio.iloc[-1]) if not pd.isna(vol_ratio.iloc[-1]) and vol_avg20.iloc[-1] > 0 else 1.0
    recent_vol_ratio = float(vol_ratio.tail(5).mean()) if not pd.isna(vol_ratio.tail(5).mean()) and vol_avg20.iloc[-1] > 0 else 1.0

    # OBV/ADL/VPT slopes (last 10 sessions)
    obv_slope = _slope(obv, 10)
    adl_slope = _slope(adl, 10)
    vpt_slope = _slope(vpt, 10)

    # MFI regime & trend
    latest_mfi = float(mfi.iloc[-1]) if not pd.isna(mfi.iloc[-1]) else 50.0
    mfi_slope = _slope(mfi.bfill().fillna(50), 10)

    # Price/volatility context with robust handling
    close = float(df["Close"].iloc[-1])
    high_20 = float(df["High"].rolling(20).max().iloc[-1])
    low_20  = float(df["Low"].rolling(20).min().iloc[-1])
    ema20_now = float(ema20.iloc[-1]) if not pd.isna(ema20.iloc[-1]) else close
    sma50_now = float(sma50.iloc[-1]) if sma50 is not None and not pd.isna(sma50.iloc[-1]) else None

    # ATR calculation with fallback
    if not pd.isna(atr14.iloc[-1]) and atr14.iloc[-1] > 0:
        atr_now = float(atr14.iloc[-1])
    else:
        # Fallback: use recent range average
        recent_range = (df["High"] - df["Low"]).tail(14)
        atr_now = float(recent_range.mean()) if recent_range.mean() > 0 else close * 0.02  # 2% of price as last resort

    # Compression (range << ATR) & absorption (small body with big volume)
    rng = df["High"] - df["Low"]
    body = (df["Close"] - df["Open"]).abs()
    # Prevent division by zero in body ratio calculation
    rng_safe = rng.replace(0, 1e-6)
    body_ratio = (body / rng_safe).fillna(0)

    # Absorption: small body relative to range + high volume
    latest_body_ratio = float(body_ratio.iloc[-1]) if not pd.isna(body_ratio.iloc[-1]) else 0.5
    is_absorption = (latest_body_ratio <= 0.3) and (latest_vol_ratio >= 1.5)

    # ATR as percentage of price
    atr_pct = atr_now / close if close > 0 else 0.0
    last_range = float(rng.iloc[-1]) if not pd.isna(rng.iloc[-1]) else 0.0

    # Compression: narrow range compared to ATR
    is_compression = (last_range <= 0.6 * atr_now) if atr_now > 0 else False

    # Breakout readiness
    is_breakout_now = (close > high_20) and (latest_vol_ratio >= 1.5)
    is_above_ema20 = close > ema20_now
    is_above_sma50 = (sma50_now is None) or (close > sma50_now)

    # Score components (weights sum to 100)
    score = 0
    signals = {}

    # 1) Flow (35): OBV/ADL/VPT slopes
    flow_sub = 0
    for s in (obv_slope, adl_slope, vpt_slope):
        if s > 0:
            flow_sub += 12
        elif s > -0.02:
            flow_sub += 6
        # else 0
    flow_sub = min(flow_sub, 35)
    score += flow_sub
    signals["flow"] = {
        "obv_slope": round(obv_slope, 4),
        "adl_slope": round(adl_slope, 4),
        "vpt_slope": round(vpt_slope, 4)
    }

    # 2) Volume pressure (20): spikes & persistence
    vol_sub = 0
    if latest_vol_ratio >= 2.0:
        vol_sub += 12
    elif latest_vol_ratio >= 1.5:
        vol_sub += 8
    elif recent_vol_ratio >= 1.2:
        vol_sub += 5
    score += min(vol_sub, 20)
    signals["volume"] = {
        "latest_vol_ratio": round(latest_vol_ratio, 2),
        "recent_vol_ratio": round(recent_vol_ratio, 2)
    }

    # 3) MFI regime/trend (15)
    mfi_sub = 0
    if 40 <= latest_mfi <= 65 and mfi_slope > 0:
        mfi_sub = 15
        mfi_state = "ACCUMULATING"
    elif latest_mfi < 35 and mfi_slope > 0:
        mfi_sub = 10
        mfi_state = "RELOADING_FROM_OVERSOLD"
    elif latest_mfi > 70 and mfi_slope < 0:
        mfi_sub = 3
        mfi_state = "DISTRIBUTION_RISK"
    else:
        mfi_sub = 7
        mfi_state = "NEUTRAL"
    score += mfi_sub
    signals["mfi"] = {"value": round(latest_mfi, 2), "trend": round(mfi_slope, 4), "state": mfi_state}

    # 4) Structure (20): trend & compression/absorption/breakout
    struct_sub = 0
    if is_above_ema20:
        struct_sub += 7
    if is_above_sma50:
        struct_sub += 5
    if is_compression:
        struct_sub += 4
    if is_absorption:
        struct_sub += 4
    score += min(struct_sub, 20)
    signals["structure"] = {
        "above_ema20": is_above_ema20,
        "above_sma50": is_above_sma50,
        "compression": is_compression,
        "absorption": is_absorption
    }

    # 5) Trigger (10): immediate breakout readiness
    trig_sub = 10 if is_breakout_now else 0
    score += trig_sub
    signals["trigger"] = {"breakout_now": is_breakout_now}

    score = int(round(min(score, 100), 0))

    # Phase detection (Wyckoff-ish)
    if is_breakout_now and flow_sub >= 24 and latest_vol_ratio >= 1.5:
        phase = "MARKUP"
    elif (flow_sub >= 20) and (40 <= latest_mfi <= 65) and (is_above_ema20 or is_compression or is_absorption):
        phase = "ACCUMULATION"
    elif (latest_mfi > 70 and mfi_slope < 0) or (flow_sub <= 12 and not is_above_ema20):
        phase = "DISTRIBUTION"
    else:
        phase = "MARKDOWN"

    # Actionable levels & risk (ATR-based)
    breakout_level = high_20
    support_level = ema20_now
    stop_buffer = 1.5 * atr_now
    takeprofit_buffer = 3.0 * atr_now  # 2R target if SL = 1.5 ATR → TP ≈ 3 ATR

    # Best-practice entry suggestions
    if phase == "ACCUMULATION":
        setup = "BUY_STOP_BREAKOUT"
        entry_note = "Place buy-stop slightly above 20-day high when volume>1.5x avg; confirmation if OBV keeps rising."
    elif phase == "MARKUP":
        setup = "BUY_PULLBACK_TO_EMA20"
        entry_note = "Enter on shallow pullback to EMA20 with shrinking volume; avoid if OBV/ADL roll over."
    elif phase == "DISTRIBUTION":
        setup = "AVOID_OR_TAKE_PROFIT"
        entry_note = "Weak flow / distribution risk; avoid new longs or trail stops tighter."
    else:
        setup = "WAIT"
        entry_note = "Wait for compression + volume thrust and OBV turn."

    return {
        "score": score,
        "phase": phase,
        "signals": signals,
        "setup": {
            "type": setup,
            "guidance": entry_note
        },
        "risk": {
            "atr": round(atr_now, 4),
            "atr_pct": round(atr_pct * 100, 2),
            "suggested_stop_atr": 1.5,
            "suggested_tp_atr": 3.0
        },
        "levels": {
            "breakout": round(breakout_level, 4),
            "support_ema20": round(support_level, 4),
            "recent_low_20": round(low_20, 4),
            "price": round(close, 4)
        }
    }


def format_mandiri_style_report(symbol: str, period: str = "6mo") -> str:
    """
    Generate Mandiri Sekuritas-style analysis report
    Combines technical indicators, bandarmology, and price data into narrative format
    """
    ticker = ensure_idx_ticker(symbol)
    stock = yf.Ticker(ticker)

    # Get all data
    hist = stock.history(period=period)
    if hist.empty or len(hist) < 50:
        return f"Insufficient data for {symbol}"

    info = stock.info

    # Calculate technical indicators
    # RSI
    rsi_indicator = RSIIndicator(close=hist['Close'], window=14)
    hist['RSI'] = rsi_indicator.rsi()

    # MACD
    macd_indicator = MACD(close=hist['Close'])
    hist['MACD'] = macd_indicator.macd()
    hist['MACD_signal'] = macd_indicator.macd_signal()
    hist['MACD_hist'] = macd_indicator.macd_diff()

    # Moving Averages
    sma_20 = SMAIndicator(close=hist['Close'], window=20)
    sma_50 = SMAIndicator(close=hist['Close'], window=50)
    sma_200 = SMAIndicator(close=hist['Close'], window=200) if len(hist) >= 200 else None
    ema_20 = EMAIndicator(close=hist['Close'], window=20)
    hist['SMA_20'] = sma_20.sma_indicator()
    hist['SMA_50'] = sma_50.sma_indicator()
    hist['SMA_200'] = sma_200.sma_indicator() if sma_200 is not None else None
    hist['EMA_20'] = ema_20.ema_indicator()

    # Bollinger Bands
    bb_indicator = BollingerBands(close=hist['Close'], window=20, window_dev=2)
    hist['BB_upper'] = bb_indicator.bollinger_hband()
    hist['BB_middle'] = bb_indicator.bollinger_mavg()
    hist['BB_lower'] = bb_indicator.bollinger_lband()

    # Get Bandarmology
    band = calculate_bandarmology(hist)

    # Latest values
    latest = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else latest

    # Calculate metrics
    current_price = float(latest['Close'])
    price_change = current_price - float(prev['Close'])
    price_change_pct = (price_change / float(prev['Close'])) * 100

    # Volume analysis
    avg_volume = int(hist['Volume'].tail(20).mean())
    current_volume = int(latest['Volume'])
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

    # BB overextension
    bb_upper = float(latest['BB_upper'])
    bb_middle = float(latest['BB_middle'])
    bb_lower = float(latest['BB_lower'])
    bb_width = bb_upper - bb_lower
    bb_overextension = ((current_price - bb_upper) / bb_upper * 100) if current_price > bb_upper else 0

    # RSI status
    rsi = float(latest['RSI'])
    if rsi > 70:
        rsi_status = "OVERBOUGHT"
        rsi_warning = "⚠️"
    elif rsi < 30:
        rsi_status = "OVERSOLD"
        rsi_warning = "✅"
    else:
        rsi_status = "NEUTRAL"
        rsi_warning = ""

    # MACD status
    macd = float(latest['MACD'])
    macd_signal = float(latest['MACD_signal'])
    macd_hist = float(latest['MACD_hist'])
    macd_status = "BULLISH KUAT" if macd_hist > 0 and macd > macd_signal else "BEARISH"

    # Trend determination
    ma20 = float(latest['SMA_20'])
    ma50 = float(latest['SMA_50'])
    trend_short = "Bullish" if ma20 > ma50 else "Bearish"
    trend_medium = "Bullish" if current_price > ma50 else "Bearish"

    # Get bandarmology data
    phase = band.get("phase", "UNKNOWN")
    score = band.get("score", 0)
    setup = band.get("setup", {})
    setup_type = setup.get("type", "WAIT")
    setup_guidance = setup.get("guidance", "")
    levels = band.get("levels", {})
    risk = band.get("risk", {})
    signals = band.get("signals", {})

    # Extract bandarmology signals
    flow = signals.get("flow", {})
    volume_sig = signals.get("volume", {})
    mfi_sig = signals.get("mfi", {})

    obv_slope = flow.get("obv_slope", 0)
    adl_slope = flow.get("adl_slope", 0)
    vpt_slope = flow.get("vpt_slope", 0)

    latest_vol_ratio = volume_sig.get("latest_vol_ratio", 1.0)

    mfi_value = mfi_sig.get("value", 50)
    mfi_state = mfi_sig.get("state", "NEUTRAL")

    # ATR for risk
    atr = risk.get("atr", 0)
    atr_pct = risk.get("atr_pct", 0)

    # Levels
    breakout_level = levels.get("breakout", current_price)
    support_ema20 = levels.get("support_ema20", current_price * 0.95)

    # Calculate entry/SL/TP
    if setup_type == "BUY_STOP_BREAKOUT":
        entry = breakout_level * 1.005  # Slightly above breakout
        stop_loss = support_ema20
        take_profit = entry + (entry - stop_loss) * 2  # 1:2 R:R
        action = "BUY"
    elif setup_type == "BUY_PULLBACK_TO_EMA20":
        entry = support_ema20
        stop_loss = entry - (atr * 1.5)
        take_profit = entry + (atr * 3.0)
        action = "BUY"
    elif setup_type == "AVOID_OR_TAKE_PROFIT":
        entry = current_price
        stop_loss = entry * 0.97
        take_profit = entry * 1.01
        action = "AVOID/SELL"
    else:
        entry = current_price
        stop_loss = entry * 0.95
        take_profit = entry * 1.05
        action = "WAIT"

    # Format report
    report = f"""
{'='*70}
{symbol} - {action} (Day Trade) {'🔥' if score >= 70 else '📊'}
Date: {datetime.now().strftime('%d %B %Y')}
{'='*70}

📊 CHART SETUP:
Close: {current_price:,.0f} ({price_change_pct:+.2f}%)
Target: {take_profit:,.0f} | Stop Loss: {stop_loss:,.0f}
Support: {support_ema20:,.0f} (EMA20) | Resistance: {breakout_level:,.0f} (20-day high)

📈 TECHNICAL INDICATORS:
RSI(14): {rsi:.2f} → {rsi_status} {rsi_warning}
MACD: {macd:.2f} / Signal: {macd_signal:.2f} → Histogram {macd_hist:+.2f} ({macd_status})
MA20: {ma20:,.0f} | MA50: {ma50:,.0f} → Harga {'di atas' if current_price > ma50 else 'di bawah'} MA (trend {trend_medium})
Bollinger Bands:
  Upper: {bb_upper:,.0f} | Middle: {bb_middle:,.0f} | Lower: {bb_lower:,.0f}
  → {'Harga TEMBUS BB Upper' if current_price > bb_upper else 'Harga dalam BB range'} {f'(+{bb_overextension:.1f}% overextension) ⚠️' if bb_overextension > 0 else ''}

🎯 BANDARMOLOGY ANALYSIS:
Score: {score}/100 ({'STRONG SETUP' if score >= 70 else 'MODERATE' if score >= 50 else 'WEAK'})
Phase: {phase}
OBV Slope: {obv_slope:+.4f} ({'Smart money accumulation ✅' if obv_slope > 0 else 'Distribution ⚠️'})
ADL Slope: {adl_slope:+.4f} ({'Accumulation line rising ✅' if adl_slope > 0 else 'Distribution'})
VPT Slope: {vpt_slope:+.4f} ({'Volume confirming price ✅' if vpt_slope > 0 else 'Divergence'})
MFI: {mfi_value:.1f} → {mfi_state}
Volume Spike: {latest_vol_ratio:.1f}x average ({current_volume:,} vs {avg_volume:,} avg) {'🚀' if latest_vol_ratio >= 2.0 else '✅' if latest_vol_ratio >= 1.5 else ''}

📋 TRADING SETUP:
Type: {setup_type}
Entry: {entry:,.0f}
Stop Loss: {stop_loss:,.0f} (Risk: {((entry - stop_loss) / entry * 100):.2f}%)
Take Profit: {take_profit:,.0f} (Reward: {((take_profit - entry) / entry * 100):.2f}%)
Risk:Reward: 1:{((take_profit - entry) / (entry - stop_loss) if entry > stop_loss else 1):.1f}

💬 REASONING:
{setup_guidance}

{'⚠️ RISK FACTORS:' if rsi_status == 'OVERBOUGHT' or bb_overextension > 0 else '✅ POSITIVE SIGNALS:'}
{f'- RSI {rsi:.2f} = Overbought territory' if rsi_status == 'OVERBOUGHT' else ''}
{f'- Harga tembus BB Upper +{bb_overextension:.1f}% (overextension risk)' if bb_overextension > 0 else ''}
{f'- Volume spike {latest_vol_ratio:.1f}x = Strong buying pressure ✅' if latest_vol_ratio >= 1.5 else ''}
{f'- {phase} phase detected with score {score}/100' if score >= 60 else ''}

📊 TECHNICAL TRENDS:
| Timeframe      | Trend     | Reasoning                                    |
|----------------|-----------|----------------------------------------------|
| Short term     | {trend_short:9} | MA20 vs MA50 crossover                       |
| Medium term    | {trend_medium:9} | Price vs MA50 position                       |
| Long term      | {'Bullish' if latest['SMA_200'] and current_price > latest['SMA_200'] else 'Bearish' if latest['SMA_200'] else 'N/A':9} | Price vs MA200 position                      |

{'='*70}
"""

    return report


def check_global_markets() -> Dict[str, Any]:
    """
    Check global markets that significantly impact IDX:
    - US Market (S&P500)
    - Key Asian markets (Nikkei, Hang Seng)
    - Commodities (Coal, Nickel via proxies)
    """
    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M WIB"),
        "us_market": {},
        "asia_markets": {},
        "commodities": {},
        "overall_sentiment": "NEUTRAL"
    }

    try:
        # US Market - S&P500
        sp500 = yf.Ticker("^GSPC")
        sp500_hist = sp500.history(period="5d")
        if not sp500_hist.empty and len(sp500_hist) >= 2:
            latest = sp500_hist.iloc[-1]['Close']
            prev = sp500_hist.iloc[-2]['Close']
            change_pct = ((latest - prev) / prev) * 100

            result["us_market"] = {
                "index": "S&P500",
                "change_pct": round(change_pct, 2),
                "sentiment": "POSITIVE" if change_pct > 0.5 else "NEGATIVE" if change_pct < -0.5 else "NEUTRAL"
            }
    except Exception as e:
        logger.warning(f"Failed to fetch US market data: {e}")
        result["us_market"] = {"error": "Data unavailable"}

    try:
        # Nikkei 225
        nikkei = yf.Ticker("^N225")
        nikkei_hist = nikkei.history(period="5d")
        if not nikkei_hist.empty and len(nikkei_hist) >= 2:
            latest = nikkei_hist.iloc[-1]['Close']
            prev = nikkei_hist.iloc[-2]['Close']
            change_pct = ((latest - prev) / prev) * 100

            result["asia_markets"]["nikkei"] = {
                "change_pct": round(change_pct, 2),
                "sentiment": "POSITIVE" if change_pct > 0 else "NEGATIVE"
            }
    except Exception as e:
        logger.warning(f"Failed to fetch Nikkei data: {e}")

    try:
        # Coal proxy - ARCH Coal or use generic commodity index
        # For simplicity, we'll use broad commodity ETF as proxy
        commodity = yf.Ticker("DBC")  # Invesco DB Commodity Index
        comm_hist = commodity.history(period="5d")
        if not comm_hist.empty and len(comm_hist) >= 2:
            latest = comm_hist.iloc[-1]['Close']
            prev = comm_hist.iloc[-2]['Close']
            change_pct = ((latest - prev) / prev) * 100

            result["commodities"]["general"] = {
                "change_pct": round(change_pct, 2),
                "sentiment": "POSITIVE" if change_pct > 1 else "NEGATIVE" if change_pct < -1 else "NEUTRAL"
            }
    except Exception as e:
        logger.warning(f"Failed to fetch commodity data: {e}")

    # Determine overall sentiment
    positive_signals = 0
    total_signals = 0

    if "sentiment" in result["us_market"]:
        total_signals += 1
        if result["us_market"]["sentiment"] == "POSITIVE":
            positive_signals += 1

    for market in result["asia_markets"].values():
        if "sentiment" in market:
            total_signals += 1
            if market["sentiment"] == "POSITIVE":
                positive_signals += 1

    for comm in result["commodities"].values():
        if "sentiment" in comm:
            total_signals += 1
            if comm["sentiment"] == "POSITIVE":
                positive_signals += 1

    if total_signals > 0:
        positive_ratio = positive_signals / total_signals
        if positive_ratio >= 0.6:
            result["overall_sentiment"] = "POSITIVE"
        elif positive_ratio <= 0.4:
            result["overall_sentiment"] = "NEGATIVE"

    return result


def get_wib_time_context() -> Dict[str, Any]:
    """
    Get current WIB time and determine trading context
    Returns session info and recommended strategy
    """
    # For simplicity, using system time (assumes server runs in WIB or adjust accordingly)
    # In production, you'd use pytz for proper timezone handling
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()  # 0=Monday, 4=Friday

    is_friday = (weekday == 4)

    context = {
        "current_time_wib": now.strftime("%H:%M"),
        "is_friday": is_friday,
        "session": None,
        "recommended_strategy": None,
        "can_trade": False
    }

    # Determine session and strategy
    if hour == 8 and 45 <= minute <= 59:
        context["session"] = "PRE_OPEN"
        context["recommended_strategy"] = "PREOPEN"
        context["can_trade"] = True
        context["action"] = "Submit orders in Pre-Input window (08:45-08:58)"

    elif hour == 9 or (hour >= 9 and hour < 12):
        if is_friday and hour >= 11 and minute >= 30:
            context["session"] = "SESSION_1_CLOSED"
            context["can_trade"] = False
        else:
            context["session"] = "SESSION_1"
            context["recommended_strategy"] = "BPJS"
            context["can_trade"] = True
            context["action"] = "Look for BPJS opportunities (exit before 15:49)"

    elif hour >= 12 and hour < 13 or (hour == 13 and minute < 30):
        context["session"] = "BREAK"
        context["can_trade"] = False
        context["action"] = "Market break - prepare for Session 2"

    elif (hour == 13 and minute >= 30) or (hour >= 14 and hour < 16):
        if hour == 15 and minute >= 50:
            context["session"] = "CLOSING"
            context["can_trade"] = False
            context["action"] = "Market closing - wait for tomorrow"
        else:
            context["session"] = "SESSION_2"
            context["recommended_strategy"] = "BSJP"
            context["can_trade"] = True
            context["action"] = "Look for BSJP opportunities (hold overnight, exit tomorrow morning)"

    elif hour >= 16 or hour < 8:
        context["session"] = "AFTER_HOURS"
        context["recommended_strategy"] = "PREOPEN"
        context["can_trade"] = False
        context["action"] = "Analyze for tomorrow's pre-open"

    else:
        context["session"] = "PRE_MARKET"
        context["can_trade"] = False

    return context


# ============================================================================
# STOCK INDEX DEFINITIONS
# ============================================================================

STOCK_INDICES = {
    "LQ45": [
        # LQ45 - 45 Most Liquid Stocks
        "AADI", "ACES", "ADMR", "ADRO", "AKRA",  # A-group
        "AMMN", "AMRT", "ANTM", "ASII",  # A-group continued
        "BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRPT", "BUMI",  # B-group
        "CPIN", "CTRA",  # C-group
        "DSSA",  # D-group
        "EMTK", "EXCL",  # E-group
        "GOTO",  # G-group
        "HEAL",  # H-group
        "ICBP", "INCO", "INDF", "INKP", "ISAT", "ITMG",  # I-group
        "JPFA",  # J-group
        "KLBF",  # K-group
        "MAPI", "MBMA", "MDKA", "MEDC",  # M-group
        "NCKL",  # N-group
        "PGAS", "PGEO", "PTBA",  # P-group
        "SCMA", "SMGR",  # S-group
        "TLKM", "TOWR",  # T-group
        "UNTR", "UNVR"  # U-group
    ],
    "IDX30": [
        # IDX30 - 30 Blue Chip Stocks
        "AADI", "ADRO", "AMRT", "ANTM", "ASII",  # A-group
        "BBCA", "BBNI", "BBRI", "BMRI", "BRPT",  # B-group
        "CPIN",  # C-group
        "GOTO",  # G-group
        "ICBP", "INCO", "INDF", "INKP", "ISAT", "ITMG",  # I-group
        "JPFA",  # J-group
        "KLBF",  # K-group
        "MBMA", "MDKA", "MEDC",  # M-group
        "PGAS", "PGEO", "PTBA",  # P-group
        "SMGR",  # S-group
        "TLKM",  # T-group
        "UNTR", "UNVR"  # U-group
    ]
}


def get_all_idx_stocks(stock_index: Optional[str] = None) -> List[str]:
    """
    Fetch Indonesian stock symbols based on index filter.
    """
    # If specific index requested, return that index
    if stock_index and stock_index.upper() in STOCK_INDICES:
        stocks = STOCK_INDICES[stock_index.upper()]
        logger.info(f"Using {stock_index.upper()} index with {len(stocks)} stocks")
        return stocks

    # Default: Return combination of LQ45 and IDX30 (best indices)
    # Use set to avoid duplicates, then convert to sorted list
    combined_stocks = set(STOCK_INDICES["LQ45"] + STOCK_INDICES["IDX30"])
    stock_list = sorted(list(combined_stocks))
    logger.info(f"Using combined LQ45+IDX30 indices with {len(stock_list)} unique stocks")
    return stock_list


# ============================================================================
# TRADING STRATEGY SCREENING FUNCTIONS
# ============================================================================

def screen_preopen_setups(stock_list: List[str], limit: int = 10, min_score: int = 70, min_avg_volume: int = 1000000, enable_bandarmology: bool = True) -> List[Dict[str, Any]]:
    """
    Screen for PRE-OPEN setups (analyzed malem kemarin, execute di 08:45-08:58)
    """
    logger.info(f"Screening {len(stock_list)} stocks for PRE-OPEN setups (bandarmology: {enable_bandarmology})...")

    # Get global market context
    global_context = check_global_markets()
    global_positive = (global_context["overall_sentiment"] == "POSITIVE")

    candidates = []

    for symbol in stock_list:
        try:
            ticker = ensure_idx_ticker(symbol)
            stock = yf.Ticker(ticker)

            # Add small delay to avoid rate limiting
            time.sleep(0.2)

            hist = stock.history(period="1mo")

            if hist.empty or len(hist) < 40:
                continue

            # Check average volume (20-day)
            avg_volume = hist['Volume'].tail(20).mean()
            if avg_volume < min_avg_volume:
                continue

            # Check yesterday's closing strength
            latest = hist.iloc[-1]
            yesterday_high = float(latest['High'])
            yesterday_close = float(latest['Close'])

            closing_strength = (yesterday_close / yesterday_high) * 100 if yesterday_high > 0 else 0

            # Strong close = within 2% of HOD
            if closing_strength < 98:
                continue

            # Calculate simple ATR for risk management
            atr_indicator = AverageTrueRange(high=hist['High'], low=hist['Low'], close=hist['Close'], window=14)
            atr = atr_indicator.average_true_range().iloc[-1]

            # Conditionally get bandarmology
            if enable_bandarmology:
                band = calculate_bandarmology(hist)
                phase = band.get("phase", "")
                score = band.get("score", 0)

                # Pre-open specific checks
                if score < min_score:
                    continue

                # Must be ACCUMULATION or MARKUP
                if phase not in ["ACCUMULATION", "MARKUP"]:
                    continue

                # Check for compression
                signals = band.get("signals", {})
                structure = signals.get("structure", {})
                has_compression = structure.get("compression", False)
                has_absorption = structure.get("absorption", False)
            else:
                # Simple mode without bandarmology
                score = None
                phase = None
                has_compression = None
                has_absorption = None

            # Calculate suggested pre-open price
            # If global positive, anticipate gap up
            gap_anticipation = 1.01 if global_positive else 1.005
            suggested_preopen = yesterday_close * gap_anticipation

            stop_loss = yesterday_close - (atr * 1.5)
            take_profit_quick = yesterday_close * 1.03  # 3% quick exit
            take_profit_ride = yesterday_close + (atr * 3.0)  # Ride momentum

            candidate = {
                "symbol": symbol,
                "yesterday_close": round(yesterday_close, 0),
                "suggested_preopen_bid": round(suggested_preopen, 0),
                "stop_loss": round(stop_loss, 0),
                "take_profit_scenarios": {
                    "quick_exit_3pct": round(take_profit_quick, 0),
                    "ride_momentum": round(take_profit_ride, 0)
                },
                "closing_strength_pct": round(closing_strength, 1),
                "global_catalyst": global_positive,
                "reasoning": f"Strong close at {closing_strength:.1f}% of HOD. "
                            f"{'Global markets positive overnight. ' if global_positive else ''}"
            }

            # Add bandarmology fields if enabled
            if enable_bandarmology:
                candidate["score"] = score
                candidate["phase"] = phase
                candidate["compression"] = has_compression
                candidate["absorption"] = has_absorption
                candidate["reasoning"] = f"{'Compression bars ready for breakout. ' if has_compression else ''}" + candidate["reasoning"] + f" {phase} phase with score {score}/100."

            candidates.append(candidate)

        except Exception as e:
            logger.warning(f"Error screening {symbol} for pre-open: {e}")
            continue

    # Sort by score if bandarmology enabled, otherwise by closing strength
    if enable_bandarmology:
        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    else:
        candidates.sort(key=lambda x: x["closing_strength_pct"], reverse=True)

    return candidates[:limit]


def screen_bpjs_setups(stock_list: List[str], limit: int = 10, min_score: int = 65, min_avg_volume: int = 1000000, enable_bandarmology: bool = True) -> List[Dict[str, Any]]:
    """
    Screen for BPJS (Beli Pagi Jual Sore) setups
    """
    logger.info(f"Screening {len(stock_list)} stocks for BPJS setups (bandarmology: {enable_bandarmology})...")

    candidates = []

    for symbol in stock_list:
        try:
            ticker = ensure_idx_ticker(symbol)
            stock = yf.Ticker(ticker)

            # Add small delay to avoid rate limiting (0.2 seconds between requests)
            time.sleep(0.2)

            hist = stock.history(period="1mo")

            if hist.empty or len(hist) < 50:
                continue

            # Check average volume (20-day)
            avg_volume = hist['Volume'].tail(20).mean()
            if avg_volume < min_avg_volume:
                continue

            # Calculate indicators
            rsi_indicator = RSIIndicator(close=hist['Close'], window=14)
            hist['RSI'] = rsi_indicator.rsi()

            macd_indicator = MACD(close=hist['Close'])
            hist['MACD'] = macd_indicator.macd()
            hist['MACD_signal'] = macd_indicator.macd_signal()

            latest = hist.iloc[-1]
            rsi = float(latest['RSI'])
            macd = float(latest['MACD'])
            macd_signal = float(latest['MACD_signal'])

            # RSI check - not overbought
            if rsi >= 70:
                continue

            # MACD check - bullish
            if macd <= macd_signal:
                continue

            current_price = float(latest['Close'])

            # Calculate simple ATR for risk management
            atr_indicator = AverageTrueRange(high=hist['High'], low=hist['Low'], close=hist['Close'], window=14)
            atr = atr_indicator.average_true_range().iloc[-1]

            # Conditionally get bandarmology
            if enable_bandarmology:
                band = calculate_bandarmology(hist)
                phase = band.get("phase", "")
                score = band.get("score", 0)

                if score < min_score:
                    continue

                # Prefer MARKUP or late ACCUMULATION
                if phase not in ["MARKUP", "ACCUMULATION"]:
                    continue

                # Volume check
                signals = band.get("signals", {})
                volume_sig = signals.get("volume", {})
                latest_vol_ratio = volume_sig.get("latest_vol_ratio", 1.0)

                # Want volume spike
                if latest_vol_ratio < 1.5:
                    continue
            else:
                # Simple mode without bandarmology
                score = None
                phase = None
                latest_vol_ratio = latest['Volume'] / avg_volume

            # Risk management
            entry = current_price
            stop_loss = entry - (atr * 1.0)  # Tight for intraday
            take_profit = entry + (atr * 1.5)  # Quick target

            risk_pct = ((entry - stop_loss) / entry) * 100
            reward_pct = ((take_profit - entry) / entry) * 100
            rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0

            candidate = {
                "symbol": symbol,
                "entry": round(entry, 0),
                "stop_loss": round(stop_loss, 0),
                "take_profit": round(take_profit, 0),
                "risk_pct": round(risk_pct, 2),
                "reward_pct": round(reward_pct, 2),
                "risk_reward": f"1:{rr_ratio:.1f}",
                "rsi": round(rsi, 1),
                "exit_deadline": "Before 15:49 WIB (avoid overnight risk)",
                "reasoning": f"MACD bullish crossover. RSI {rsi:.1f} (not overbought). Exit mandatory before market close."
            }

            # Add bandarmology fields if enabled
            if enable_bandarmology:
                candidate["score"] = score
                candidate["phase"] = phase
                candidate["volume_spike"] = f"{latest_vol_ratio:.1f}x"
                candidate["reasoning"] = f"Volume spike {latest_vol_ratio:.1f}x with MACD bullish. RSI {rsi:.1f} (not overbought). {phase} phase. Exit mandatory before market close."

            candidates.append(candidate)

        except Exception as e:
            # Log warning but continue with other stocks
            # Common errors: rate limiting, delisted stocks, insufficient data
            logger.warning(f"Error screening {symbol} for BPJS: {e}")
            continue

    # Sort by score if bandarmology enabled, otherwise by RSI (lower is better)
    if enable_bandarmology:
        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    else:
        candidates.sort(key=lambda x: x["rsi"], reverse=False)

    return candidates[:limit]


def screen_bsjp_setups(stock_list: List[str], limit: int = 10, min_score: int = 60, min_avg_volume: int = 1000000, enable_bandarmology: bool = True) -> List[Dict[str, Any]]:
    """
    Screen for BSJP (Beli Sore Jual Pagi) setups
    """
    logger.info(f"Screening {len(stock_list)} stocks for BSJP setups (bandarmology: {enable_bandarmology})...")

    candidates = []

    for symbol in stock_list:
        try:
            ticker = ensure_idx_ticker(symbol)
            stock = yf.Ticker(ticker)

            # Add small delay to avoid rate limiting
            time.sleep(0.2)

            hist = stock.history(period="3mo")

            if hist.empty or len(hist) < 50:
                continue

            # Check average volume (20-day)
            avg_volume = hist['Volume'].tail(20).mean()
            if avg_volume < min_avg_volume:
                continue

            # Calculate RSI
            rsi_indicator = RSIIndicator(close=hist['Close'], window=14)
            hist['RSI'] = rsi_indicator.rsi()

            latest = hist.iloc[-1]
            rsi = float(latest['RSI'])

            # RSI check - not overextended
            if rsi >= 65:
                continue

            # Check closing strength (near HOD)
            today_high = float(latest['High'])
            today_close = float(latest['Close'])
            closing_strength = (today_close / today_high) * 100 if today_high > 0 else 0

            # Want strong close (within 1% of HOD)
            if closing_strength < 99:
                continue

            # Calculate simple ATR for risk management
            atr_indicator = AverageTrueRange(high=hist['High'], low=hist['Low'], close=hist['Close'], window=14)
            atr = atr_indicator.average_true_range().iloc[-1]

            # Conditionally get bandarmology
            if enable_bandarmology:
                band = calculate_bandarmology(hist)
                phase = band.get("phase", "")
                score = band.get("score", 0)

                if score < min_score:
                    continue

                # Prefer ACCUMULATION (patient overnight play)
                if phase != "ACCUMULATION":
                    continue

                # Check for compression/absorption
                signals = band.get("signals", {})
                structure = signals.get("structure", {})
                has_compression = structure.get("compression", False)
                has_absorption = structure.get("absorption", False)

                # Want at least one
                if not (has_compression or has_absorption):
                    continue
            else:
                # Simple mode without bandarmology
                score = None
                phase = None
                has_compression = None
                has_absorption = None

            # Risk management - wider for overnight
            entry = today_close
            stop_loss = entry - (atr * 2.0)  # Wider for overnight
            take_profit = entry + (atr * 3.0)  # Target gap up

            risk_pct = ((entry - stop_loss) / entry) * 100
            reward_pct = ((take_profit - entry) / entry) * 100
            rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0

            candidate = {
                "symbol": symbol,
                "entry": round(entry, 0),
                "stop_loss": round(stop_loss, 0),
                "take_profit": round(take_profit, 0),
                "risk_pct": round(risk_pct, 2),
                "reward_pct": round(reward_pct, 2),
                "risk_reward": f"1:{rr_ratio:.1f}",
                "rsi": round(rsi, 1),
                "closing_strength_pct": round(closing_strength, 1),
                "exit_window_tomorrow": "09:00-11:30 WIB",
                "overnight_risks": [
                    "Monitor global markets (US close, Asia open)",
                    "Check for corporate news before market open",
                    "Set alerts for stop loss"
                ],
                "reasoning": f"Strong close at {closing_strength:.1f}% of HOD. RSI {rsi:.1f} (room to run). Target gap up tomorrow morning."
            }

            # Add bandarmology fields if enabled
            if enable_bandarmology:
                candidate["score"] = score
                candidate["phase"] = phase
                candidate["compression"] = has_compression
                candidate["absorption"] = has_absorption
                candidate["reasoning"] = f"Strong close at {closing_strength:.1f}% of HOD. {'Compression detected. ' if has_compression else ''}{'Absorption bars present. ' if has_absorption else ''}{phase} phase (coiling for breakout). RSI {rsi:.1f} (room to run). Target gap up tomorrow morning."

            candidates.append(candidate)

        except Exception as e:
            logger.warning(f"Error screening {symbol} for BSJP: {e}")
            continue

    # Sort by score if bandarmology enabled, otherwise by closing strength
    if enable_bandarmology:
        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    else:
        candidates.sort(key=lambda x: x["closing_strength_pct"], reverse=True)

    return candidates[:limit]


def detect_pattern_label(hist: pd.DataFrame, symbol: str) -> str:
    """
    Detect common technical patterns and return simple 2-4 word label
    """
    if hist.empty or len(hist) < 50:
        return "Technical Setup"

    try:
        # Calculate indicators
        close = hist['Close']

        # Moving averages
        ma20 = SMAIndicator(close=close, window=20).sma_indicator()
        ma50 = SMAIndicator(close=close, window=50).sma_indicator()
        ma200 = SMAIndicator(close=close, window=200).sma_indicator() if len(hist) >= 200 else None

        # MACD
        macd_ind = MACD(close=close)
        macd = macd_ind.macd()
        macd_signal = macd_ind.macd_signal()

        # Volume
        volume = hist['Volume']
        vol_avg20 = volume.rolling(20).mean()

        # Latest values
        latest_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2]) if len(close) > 1 else latest_price
        latest_ma20 = float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else 0
        latest_ma50 = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else 0
        latest_ma200 = float(ma200.iloc[-1]) if ma200 is not None and not pd.isna(ma200.iloc[-1]) else 0

        prev_ma50 = float(ma50.iloc[-2]) if len(ma50) > 1 and not pd.isna(ma50.iloc[-2]) else latest_ma50
        prev_ma200 = float(ma200.iloc[-2]) if ma200 is not None and len(ma200) > 1 and not pd.isna(ma200.iloc[-2]) else latest_ma200

        latest_macd = float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else 0
        latest_macd_signal = float(macd_signal.iloc[-1]) if not pd.isna(macd_signal.iloc[-1]) else 0
        prev_macd = float(macd.iloc[-2]) if len(macd) > 1 and not pd.isna(macd.iloc[-2]) else latest_macd
        prev_macd_signal = float(macd_signal.iloc[-2]) if len(macd_signal) > 1 and not pd.isna(macd_signal.iloc[-2]) else latest_macd_signal

        latest_volume = float(volume.iloc[-1])
        avg_volume = float(vol_avg20.iloc[-1]) if not pd.isna(vol_avg20.iloc[-1]) and vol_avg20.iloc[-1] > 0 else 1
        volume_ratio = latest_volume / avg_volume

        # Pattern detection (priority order - most specific first)

        # 1. Break Out MA200
        if latest_ma200 > 0 and latest_price > latest_ma200 and prev_price <= prev_ma200:
            return "Break Out MA200"

        # 2. Golden Cross (MA50 crosses above MA200)
        if latest_ma200 > 0 and latest_ma50 > latest_ma200 and prev_ma50 <= prev_ma200:
            return "Golden Cross MA50/200"

        # 3. Volume Spike (most prominent)
        if volume_ratio >= 2.5:
            return f"Volume Spike {volume_ratio:.1f}x"
        elif volume_ratio >= 2.0:
            return f"Volume Spike {volume_ratio:.1f}x"

        # 4. MACD Bullish Cross
        if latest_macd > latest_macd_signal and prev_macd <= prev_macd_signal:
            return "MACD Bullish Cross"

        # 5. Approaching MA20 (within 1%)
        if latest_ma20 > 0 and abs(latest_price - latest_ma20) / latest_ma20 < 0.01:
            if latest_price > latest_ma20:
                return "Testing MA20 Support"
            else:
                return "Approaching MA20"

        # 6. Breakout Resistance (20-day high)
        high_20 = float(hist['High'].rolling(20).max().iloc[-1])
        if latest_price >= high_20 * 0.995:  # Within 0.5% of 20-day high
            return "Breakout Resistance"

        # 7. Above MA200 (long-term bullish)
        if latest_ma200 > 0 and latest_price > latest_ma200:
            return "Above MA200"

        # 8. Support Bounce
        low_20 = float(hist['Low'].rolling(20).min().iloc[-1])
        if latest_price <= low_20 * 1.01:  # Within 1% of 20-day low
            return "Support Bounce"

        # Default
        return "Technical Setup"

    except Exception as e:
        logger.warning(f"Error detecting pattern for {symbol}: {e}")
        return "Technical Setup"


def calculate_chart_based_levels(hist: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate support/resistance levels from chart analysis
    """
    if hist.empty or len(hist) < 50:
        latest_close = float(hist['Close'].iloc[-1]) if not hist.empty else 0
        return {
            "support": latest_close * 0.98,
            "resistance": latest_close * 1.02,
            "stop_loss": latest_close * 0.97,
            "target": latest_close * 1.03
        }

    try:
        close = hist['Close']
        high = hist['High']
        low = hist['Low']

        # Calculate MAs
        ma20 = SMAIndicator(close=close, window=20).sma_indicator()
        ma50 = SMAIndicator(close=close, window=50).sma_indicator()

        # Swing levels
        swing_high_20 = float(high.rolling(20).max().iloc[-1])
        swing_low_20 = float(low.rolling(20).min().iloc[-1])

        latest_close = float(close.iloc[-1])
        latest_ma20 = float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else latest_close
        latest_ma50 = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else latest_close

        # Support levels (choose nearest below price)
        support_candidates = []
        if latest_ma20 < latest_close:
            support_candidates.append(latest_ma20)
        if latest_ma50 < latest_close:
            support_candidates.append(latest_ma50)
        support_candidates.append(swing_low_20)

        support = max([s for s in support_candidates if s < latest_close], default=latest_close * 0.98)

        # Resistance levels (choose nearest above price)
        resistance_candidates = []
        if latest_ma20 > latest_close:
            resistance_candidates.append(latest_ma20)
        if latest_ma50 > latest_close:
            resistance_candidates.append(latest_ma50)
        resistance_candidates.append(swing_high_20)

        resistance = min([r for r in resistance_candidates if r > latest_close], default=swing_high_20)

        # Stop loss: Slightly below support (0.5% buffer)
        stop_loss = support * 0.995

        # Target: Resistance level
        target = resistance

        return {
            "support": round(support, 0),
            "resistance": round(resistance, 0),
            "stop_loss": round(stop_loss, 0),
            "target": round(target, 0)
        }

    except Exception as e:
        logger.warning(f"Error calculating chart levels: {e}")
        latest_close = float(hist['Close'].iloc[-1])
        return {
            "support": round(latest_close * 0.98, 0),
            "resistance": round(latest_close * 1.02, 0),
            "stop_loss": round(latest_close * 0.97, 0),
            "target": round(latest_close * 1.03, 0)
        }


def screen_day_trade_setups(stock_list: List[str], limit: int = 10, mode: str = "mandiri") -> List[Dict[str, Any]]:
    """
    Screen for day trade opportunities with Mandiri-style simple criteria
    """
    logger.info(f"Screening {len(stock_list)} stocks for day trade setups (mode: {mode})...")

    # Set thresholds based on mode
    if mode == "mandiri":
        rsi_threshold = 78  # More lenient
        macd_threshold = -20  # More lenient
        volume_threshold = 0.5  # More lenient
        risk_threshold = 6  # More lenient
    else:  # strict mode
        rsi_threshold = 75
        macd_threshold = -10
        volume_threshold = 0.8
        risk_threshold = 5

    candidates = []

    for symbol in stock_list:
        try:
            ticker = ensure_idx_ticker(symbol)
            stock = yf.Ticker(ticker)

            # Add small delay to avoid rate limiting
            time.sleep(0.2)

            hist = stock.history(period="3mo")

            if hist.empty or len(hist) < 50:
                continue

            # Calculate basic indicators for filtering
            close = hist['Close']
            volume = hist['Volume']

            # RSI
            rsi_ind = RSIIndicator(close=close, window=14)
            rsi = float(rsi_ind.rsi().iloc[-1]) if not rsi_ind.rsi().empty else 50

            # MACD
            macd_ind = MACD(close=close)
            macd = float(macd_ind.macd().iloc[-1]) if not macd_ind.macd().empty else 0
            macd_signal = float(macd_ind.macd_signal().iloc[-1]) if not macd_ind.macd_signal().empty else 0

            # Volume ratio
            vol_avg = volume.rolling(20).mean().iloc[-1]
            vol_ratio = float(volume.iloc[-1] / vol_avg) if vol_avg > 0 else 1.0

            # Filter criteria
            if rsi > rsi_threshold:
                continue
            if macd < macd_signal + macd_threshold:
                continue
            if vol_ratio < volume_threshold:
                continue

            # Get chart levels
            levels = calculate_chart_based_levels(hist)

            # Get pattern label
            pattern = detect_pattern_label(hist, symbol)

            # Latest price
            latest_close = float(close.iloc[-1])

            # Calculate risk/reward
            stop_loss = levels["stop_loss"]
            target = levels["target"]
            support = levels["support"]
            resistance = levels["resistance"]

            risk_amount = latest_close - stop_loss
            reward_amount = target - latest_close

            risk_pct = (risk_amount / latest_close) * 100 if latest_close > 0 else 0
            reward_pct = (reward_amount / latest_close) * 100 if latest_close > 0 else 0

            # Skip if risk too high
            if risk_pct > risk_threshold:
                continue

            # Skip if R:R too poor (<1:1)
            if reward_amount <= 0 or risk_amount <= 0:
                continue

            rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

            if rr_ratio < 1.0:
                continue

            # Determine recommendation
            recommendation = "BUY" if macd > macd_signal else "HOLD"

            candidates.append({
                "symbol": symbol,
                "recommendation": recommendation,
                "harga_penutupan": int(latest_close),
                "target_harga": int(target),
                "stop_loss": int(stop_loss),
                "support": int(support),
                "resistance": int(resistance),
                "keterangan": pattern,
                "rsi": round(rsi, 1),
                "volume_ratio": round(vol_ratio, 1),
                "risk_reward": f"1:{rr_ratio:.1f}"
            })

        except Exception as e:
            logger.warning(f"Error screening {symbol} for day trade: {e}")
            continue

    # Sort by volume ratio (most active first)
    candidates.sort(key=lambda x: x["volume_ratio"], reverse=True)

    return candidates[:limit]


def format_day_trade_table(setups: List[Dict[str, Any]], session_info: Dict[str, Any]) -> str:
    """
    Format day trade setups into Mandiri-style table
    """
    if not setups:
        return "No day trade setups found matching criteria."

    # Header
    output = f"""
{'='*90}
DAY TRADE RECOMMENDATIONS
{'='*90}
Date: {datetime.now().strftime('%d %B %Y')} | Session: {session_info.get('session', 'N/A')} | Time: {session_info.get('current_time_wib', 'N/A')}

| Saham | Rekomendasi | Harga Penutupan | Target Harga | Stop Loss | Support | Resistance | Keterangan              |
|-------|-------------|-----------------|--------------|-----------|---------|------------|-------------------------|
"""

    # Add rows
    for setup in setups:
        symbol = setup['symbol']
        rec = setup['recommendation']
        closing = f"{setup['harga_penutupan']:,}"
        target = f"{setup['target_harga']:,}"
        sl = f"{setup['stop_loss']:,}"
        support = f"{setup['support']:,}"
        resistance = f"{setup['resistance']:,}"
        keterangan = setup['keterangan']

        output += f"| {symbol:5} | {rec:11} | {closing:>15} | {target:>12} | {sl:>9} | {support:>7} | {resistance:>10} | {keterangan:23} |\n"

    # Footer with notes
    output += f"""
{'='*90}

📊 RISK MANAGEMENT:
- Stop Loss: Chart-based (below support levels)
- Target: Chart-based (resistance levels)
- Risk:Reward: Minimum 1:1, prefer 1:1.5 or better

⚠️ IMPORTANT NOTES:
- For intraday trading: EXIT before 15:49 WIB (avoid overnight risk)
- Monitor volume - prefer active stocks (volume >1.0x average)
- Set alerts at support/resistance levels
- Use proper position sizing (max 2-3% risk per trade)

{'='*90}
"""

    return output


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class StockPriceRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol (e.g., BBCA, BBRI)")


class HistoricalDataRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol")
    period: str = Field("3mo", description="Time period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max")


class TechnicalIndicatorsRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol")
    period: str = Field("6mo", description="Historical period for calculation")


class BandarmologyRequest(BaseModel):
    symbol: str = Field(..., description="IDX ticker without .JK")
    period: str = Field("6mo", description="History period: 3mo, 6mo, 1y")


class FundamentalsRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol")


class MandiriReportRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol")
    period: str = Field("6mo", description="Historical period")


class GlobalMarketsRequest(BaseModel):
    pass


class TimeContextRequest(BaseModel):
    pass


class StockListRequest(BaseModel):
    stock_index: Optional[str] = Field("BOTH", description="Stock index: LQ45, IDX30, or BOTH")


class PreopenSetupsRequest(BaseModel):
    stock_index: Optional[str] = Field("BOTH", description="Stock index: LQ45, IDX30, or BOTH")
    limit: int = Field(10, description="Number of setups to return")
    min_score: int = Field(70, description="Minimum bandarmology score")
    min_avg_volume: int = Field(1000000, description="Minimum average volume")
    enable_bandarmology: bool = Field(True, description="Enable bandarmology analysis")


class BPJSSetupsRequest(BaseModel):
    stock_index: Optional[str] = Field("BOTH", description="Stock index: LQ45, IDX30, or BOTH")
    limit: int = Field(10, description="Number of setups to return")
    min_score: int = Field(65, description="Minimum bandarmology score")
    min_avg_volume: int = Field(1000000, description="Minimum average volume")
    enable_bandarmology: bool = Field(True, description="Enable bandarmology analysis")


class BSJPSetupsRequest(BaseModel):
    stock_index: Optional[str] = Field("BOTH", description="Stock index: LQ45, IDX30, or BOTH")
    limit: int = Field(10, description="Number of setups to return")
    min_score: int = Field(60, description="Minimum bandarmology score")
    min_avg_volume: int = Field(1000000, description="Minimum average volume")
    enable_bandarmology: bool = Field(False, description="Enable bandarmology analysis")


class DayTradeSetupsRequest(BaseModel):
    stock_index: Optional[str] = Field(None, description="Stock index: LQ45, IDX30, or BOTH")
    limit: int = Field(10, description="Number of setups to return")
    mode: str = Field("mandiri", description="Screening mode: mandiri or strict")


# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.get("/")
@app.post("/")
async def root():
    """API root - returns available endpoints"""
    return {
        "name": "Indonesian Stock Analysis API",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "stock_price": "/api/stock/price",
            "historical_data": "/api/stock/history",
            "technical_indicators": "/api/stock/technicals",
            "bandarmology": "/api/stock/bandarmology",
            "fundamentals": "/api/stock/fundamentals",
            "mandiri_report": "/api/stock/mandiri-report",
            "global_markets": "/api/market/global",
            "time_context": "/api/market/time-context",
            "stock_list": "/api/market/stock-list",
            "preopen_setups": "/api/screen/preopen",
            "bpjs_setups": "/api/screen/bpjs",
            "bsjp_setups": "/api/screen/bsjp",
            "day_trade_setups": "/api/screen/day-trade",
            "get_news": "/api/news/get",
            "news_status": "/api/news/status",
            "get_news_sync": "/api/news/get/sync",
            "read_news_report": "/api/news/read",
            "read_news_report_json": "/api/news/read/json",
            "read_news_analyze": "/api/news/analyze",
            "read_news_check_files": "/api/news/check_files",
        }
    }


@app.post("/api/stock/price")
async def get_stock_price(request: StockPriceRequest):
    """Get current/latest price and basic info for Indonesian stock"""
    try:
        ticker = ensure_idx_ticker(request.symbol)
        stock = yf.Ticker(ticker)
        info = stock.info
        history = stock.history(period="1d")

        if history.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {request.symbol}")

        latest = history.iloc[-1]

        return {
            "symbol": request.symbol,
            "price": float(latest['Close']),
            "change": float(latest['Close'] - latest['Open']),
            "change_percent": float(((latest['Close'] - latest['Open']) / latest['Open']) * 100),
            "volume": int(latest['Volume']),
            "high": float(latest['High']),
            "low": float(latest['Low']),
            "open": float(latest['Open']),
            "market_cap": info.get('marketCap'),
            "currency": info.get('currency', 'IDR'),
        }
    except Exception as e:
        logger.error(f"Error getting stock price for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stock/history")
async def get_historical_data(request: HistoricalDataRequest):
    """Get historical OHLCV data"""
    try:
        ticker = ensure_idx_ticker(request.symbol)
        stock = yf.Ticker(ticker)
        history = stock.history(period=request.period)

        if history.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {request.symbol}")

        # Convert to JSON-serializable format
        data = []
        for date, row in history.iterrows():
            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": int(row['Volume']),
            })

        return {
            "symbol": request.symbol,
            "period": request.period,
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting historical data for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stock/technicals")
async def get_technical_indicators(request: TechnicalIndicatorsRequest):
    """Calculate technical indicators (RSI, MACD, MA, Bollinger Bands)"""
    try:
        ticker = ensure_idx_ticker(request.symbol)
        stock = yf.Ticker(ticker)
        history = stock.history(period=request.period)

        if history.empty or len(history) < 50:
            raise HTTPException(status_code=404, detail="Insufficient data")

        # Calculate indicators
        close = history['Close']

        rsi = RSIIndicator(close=close, window=14).rsi()
        macd_indicator = MACD(close=close)
        sma_20 = SMAIndicator(close=close, window=20).sma_indicator()
        sma_50 = SMAIndicator(close=close, window=50).sma_indicator()
        ema_12 = EMAIndicator(close=close, window=12).ema_indicator()
        bb = BollingerBands(close=close, window=20, window_dev=2)

        latest_price = float(close.iloc[-1])

        return {
            "symbol": request.symbol,
            "current_price": latest_price,
            "rsi": float(rsi.iloc[-1]) if not rsi.empty else None,
            "macd": {
                "macd": float(macd_indicator.macd().iloc[-1]),
                "signal": float(macd_indicator.macd_signal().iloc[-1]),
                "histogram": float(macd_indicator.macd_diff().iloc[-1]),
            },
            "moving_averages": {
                "sma_20": float(sma_20.iloc[-1]),
                "sma_50": float(sma_50.iloc[-1]),
                "ema_12": float(ema_12.iloc[-1]),
            },
            "bollinger_bands": {
                "upper": float(bb.bollinger_hband().iloc[-1]),
                "middle": float(bb.bollinger_mavg().iloc[-1]),
                "lower": float(bb.bollinger_lband().iloc[-1]),
            },
        }
    except Exception as e:
        logger.error(f"Error calculating technicals for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stock/bandarmology")
async def get_bandarmology(request: BandarmologyRequest):
    """Bandarmology-style analysis using OHLCV data"""
    try:
        ticker = ensure_idx_ticker(request.symbol)
        stock = yf.Ticker(ticker)
        history = stock.history(period=request.period)

        if history.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {request.symbol}")

        result = calculate_bandarmology(history)
        result['symbol'] = request.symbol

        return result
    except Exception as e:
        logger.error(f"Error calculating bandarmology for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stock/fundamentals")
async def get_fundamentals(request: FundamentalsRequest):
    """Get fundamental data (P/E, P/B, Market Cap, etc.)"""
    try:
        ticker = ensure_idx_ticker(request.symbol)
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            "symbol": request.symbol,
            "market_cap": info.get('marketCap'),
            "pe_ratio": info.get('trailingPE'),
            "pb_ratio": info.get('priceToBook'),
            "eps": info.get('trailingEps'),
            "dividend_yield": info.get('dividendYield'),
            "revenue": info.get('totalRevenue'),
            "profit_margin": info.get('profitMargins'),
            "roe": info.get('returnOnEquity'),
            "debt_to_equity": info.get('debtToEquity'),
            "current_ratio": info.get('currentRatio'),
            "beta": info.get('beta'),
        }
    except Exception as e:
        logger.error(f"Error getting fundamentals for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stock/mandiri-report")
async def get_mandiri_report(request: MandiriReportRequest):
    """Get Mandiri Sekuritas-style analysis report"""
    try:
        report = format_mandiri_style_report(request.symbol, request.period)
        return {"report": report}
    except Exception as e:
        logger.error(f"Error generating Mandiri report for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/market/global")
async def get_global_markets(request: GlobalMarketsRequest):
    """Check global markets sentiment"""
    try:
        result = check_global_markets()
        return result
    except Exception as e:
        logger.error(f"Error checking global markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/market/time-context")
async def get_time_context(request: TimeContextRequest):
    """Get current WIB time and trading session context"""
    try:
        result = get_wib_time_context()
        return result
    except Exception as e:
        logger.error(f"Error getting time context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/market/stock-list")
async def get_stock_list(request: StockListRequest):
    """Get list of Indonesian stocks by index"""
    try:
        stocks = get_all_idx_stocks(request.stock_index)
        return {
            "index": request.stock_index or "COMBINED",
            "count": len(stocks),
            "stocks": stocks
        }
    except Exception as e:
        logger.error(f"Error getting stock list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/screen/preopen")
async def screen_preopen(request: PreopenSetupsRequest):
    """Screen for PRE-OPEN setups (analyzed malem kemarin, execute di 08:45-08:58)"""
    try:
        stocks = get_all_idx_stocks(request.stock_index)
        setups = screen_preopen_setups(
            stocks,
            limit=request.limit,
            min_score=request.min_score,
            min_avg_volume=request.min_avg_volume,
            enable_bandarmology=request.enable_bandarmology
        )
        return {
            "strategy": "PREOPEN",
            "count": len(setups),
            "setups": setups
        }
    except Exception as e:
        logger.error(f"Error screening preopen setups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/screen/bpjs")
async def screen_bpjs(request: BPJSSetupsRequest):
    """Screen for BPJS (Beli Pagi Jual Sore) setups"""
    try:
        stocks = get_all_idx_stocks(request.stock_index)
        setups = screen_bpjs_setups(
            stocks,
            limit=request.limit,
            min_score=request.min_score,
            min_avg_volume=request.min_avg_volume,
            enable_bandarmology=request.enable_bandarmology
        )
        return {
            "strategy": "BPJS",
            "count": len(setups),
            "setups": setups
        }
    except Exception as e:
        logger.error(f"Error screening BPJS setups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/screen/bsjp")
async def screen_bsjp(request: BSJPSetupsRequest):
    """Screen for BSJP (Beli Sore Jual Pagi) setups"""
    try:
        stocks = get_all_idx_stocks(request.stock_index)
        setups = screen_bsjp_setups(
            stocks,
            limit=request.limit,
            min_score=request.min_score,
            min_avg_volume=request.min_avg_volume,
            enable_bandarmology=request.enable_bandarmology
        )
        return {
            "strategy": "BSJP",
            "count": len(setups),
            "setups": setups
        }
    except Exception as e:
        logger.error(f"Error screening BSJP setups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/screen/day-trade")
async def screen_day_trade(request: DayTradeSetupsRequest):
    """Screen for day trade opportunities with Mandiri-style criteria"""
    try:
        stocks = get_all_idx_stocks(request.stock_index)
        session_info = get_wib_time_context()
        setups = screen_day_trade_setups(
            stocks,
            limit=request.limit,
            mode=request.mode
        )

        # Format as table if requested
        table = format_day_trade_table(setups, session_info)

        return {
            "strategy": "DAY_TRADE",
            "mode": request.mode,
            "session": session_info,
            "count": len(setups),
            "setups": setups,
            "table": table
        }
    except Exception as e:
        logger.error(f"Error screening day trade setups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/status")
async def get_news_status():
    """Get current pipeline execution status"""
    return pipeline_status

@app.post("/api/news/get")
async def get_news(request: GetNewsRequest, background_tasks: BackgroundTasks):
    """Run the news pipeline asynchronously"""
    global pipeline_status

    if pipeline_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running. Please wait for it to complete."
        )

    background_tasks.add_task(run_pipeline, request)

    return {
        "status": "started",
        "message": "Pipeline started in background",
        "check_status_at": "/news/status",
        "read_report_at": "/news/read",
        "parameters": request.model_dump()
    }

@app.post("/api/news/get/sync")
async def get_news_sync(request: GetNewsRequest):
    """Run the news pipeline synchronously"""
    global pipeline_status

    if pipeline_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running. Please wait for it to complete."
        )

    try:
        output = run_pipeline(request)

        return {
            "status": "completed",
            "message": "Pipeline completed successfully",
            "output_file": request.output,
            "read_report_at": "/news/read",
            "pipeline_output": output
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news/read")
async def read_news_report(file: str = "news_condensed.txt"):
    """Read the condensed news report as plain text"""
    try:
        file_path = Path(f"data/{file}")

        if ".." in str(file) or file.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid file path")

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Report file not found: {file}. Have you run /news/get yet?"
            )

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return PlainTextResponse(content)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news/read/json")
async def read_news_report_json(file: str = "news_condensed.txt"):
    """Read the condensed news report as JSON with metadata"""
    try:
        file_path = Path(f"data/{file}")

        if ".." in str(file) or file.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid file path")

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Report file not found: {file}. Have you run /news/get yet?"
            )

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        stats = file_path.stat()

        return {
            "file": file,
            "content": content,
            "size_bytes": stats.st_size,
            "modified_at": datetime.fromtimestamp(stats.st_mtime).isoformat(),
            "lines": len(content.split("\n"))
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/news/analyze")
def analyze_news_with_claude(
    request: Request,
    x_secret_key: OptionalType[str] = Header(None),
    prompt: str = """
You are a financial analyst.

Please perform the following task:
1. Analyze the financial news articles focusing on:
   - Price movements and catalysts
   - Market sentiment
   - Key stock tickers mentioned
   - Dominant themes
2. Generate a comprehensive markdown report
3. Write the report to 'daily_report.md' in the current directory, make sure it has no emoji, treat as professional report
4. If 'daily_report.md' already exists, just replace (delete and write a new report)

The report should include:
- Market overview section
- Most mentioned stocks with analysis
- Top 3 actionable recommendations
- Honorable article insights with sentiment
- Be concise and data-focused
- Important - write in Bahasa Indonesia, but for special terms, use English

After writing the report, confirm it was created successfully.
""",
    file: str = "news_condensed.txt",
) -> str:
    """
    Read the condensed news from /app/data and analyze it using `claude -p` CLI.
    🔒 SECURITY: This endpoint is protected. Only accessible from localhost or with valid X-Secret-Key header.

    prompt: analysis instruction prepended before the news content.
    file: news file in /app/data/ (default: news_condensed.txt).
    """
    # Security check
    verify_claude_access(request, x_secret_key)

    import subprocess
    from pathlib import Path

    news_path = Path(f"/app/data/{file}")
    if not news_path.exists():
        return f"ERROR: {file} not found in /app/data. Run the news pipeline first."

    content = news_path.read_text(encoding="utf-8")
    full_input = f"{prompt}\n\n---\n\n{content}"

    try:
        # Write prompt to temp file for appuser to read
        temp_input = Path("/tmp/claude_input.txt")
        temp_input.write_text(full_input, encoding="utf-8")
        os.chmod(temp_input, 0o644)  # Make readable by appuser

        # Run claude as non-root user (appuser) to avoid permissions error
        result = subprocess.run(
            ["su", "-", "appuser", "-c",
             "cd /app/data && claude -p --dangerously-skip-permissions < /tmp/claude_input.txt"],
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Clean up temp file
        temp_input.unlink(missing_ok=True)

        if result.returncode != 0:
            return f"ERROR (exit {result.returncode}):\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        return result.stdout.strip()
    except FileNotFoundError:
        return "ERROR: `claude` CLI not found in container. Rebuild the Docker image."
    except subprocess.TimeoutExpired:
        return "ERROR: claude -p timed out after 300s."
    except Exception as e:
        return f"ERROR: {e}"
    
@app.get("/api/news/check_files")
def check_existing_files() -> dict:
    """
    Check which key files already exist in the data volume (/app/data).
    Use this FIRST before starting any flow to avoid redundant work:
    - If news_condensed.txt exists → skip running the news pipeline
    - If daily_report.md exists → skip running the analysis
    Returns each file's existence status and last modified time.
    """
    from pathlib import Path
    from datetime import datetime

    files = ["news_condensed.txt", "daily_report.md"]
    result = {}
    for name in files:
        path = Path(f"/app/data/{name}")
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            result[name] = {"exists": True, "last_modified": mtime}
        else:
            result[name] = {"exists": False, "last_modified": None}
    return result


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    host = "0.0.0.0"
    port = "13052"

    logger.info(f"Indonesian Stock Analysis REST API starting on {host}:{port}...")
    logger.info(f"API Documentation: http://{host}:{port}/docs")

    uvicorn.run(app, host=host, port=port)
