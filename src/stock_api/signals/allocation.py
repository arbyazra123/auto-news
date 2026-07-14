#!/usr/bin/env python3
"""
Asset allocation module: scores each asset class (0-100, 50 = neutral) and
maps the scores to recommended portfolio weights.

Asset classes:
- equity:        IDX80 equities (breadth of signals + JKSE trend)
- bonds:         INDOGB government bonds (real yield, yield momentum, curve)
- money_market:  cash instruments at ~BI rate (real cash rate, defensive)

Weights = benchmark +/- tilt proportional to (score - 50), clamped to bands
and normalized to 100%. All parameters live in ALLOCATION_CONFIG so the PM
can tune benchmark and bands without touching logic.
"""
import logging
from typing import List, Optional

import pandas as pd

logger = logging.getLogger("idx-stock-api")

ALLOCATION_CONFIG = {
    "benchmark": {"equity": 0.50, "bonds": 0.35, "money_market": 0.15},
    "bands": {
        "equity": (0.20, 0.75),
        "bonds": (0.15, 0.60),
        "money_market": (0.05, 0.40),
    },
    # Max tilt away from benchmark when a class score hits 0 or 100
    "max_tilt": 0.20,
    # Real yield (10Y - CPI) considered neutral for bonds, in pct points
    "bond_neutral_real_yield": 2.0,
    # Real cash rate (BI rate - CPI) considered neutral, in pct points
    "mm_neutral_real_rate": 1.0,
}


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# ============================================================================
# ASSET CLASS SCORES
# ============================================================================

def equity_class_score(signals: List[dict], jkse_hist: Optional[pd.DataFrame]) -> dict:
    """Equity regime score from signal breadth + JKSE index trend"""
    notes = []
    scored = [s for s in signals if s.get("score") is not None]

    if scored:
        avg_score = sum(s["score"] for s in scored) / len(scored)
        buys = sum(1 for s in scored if s["signal"] == "BUY")
        sells = sum(1 for s in scored if s["signal"] == "SELL")
        breadth = 50.0 + (buys - sells) / len(scored) * 100
        notes.append(f"{buys} BUY / {sells} SELL of {len(scored)} scored")
        notes.append(f"universe avg score {avg_score:.0f}")
    else:
        avg_score, breadth = 50.0, 50.0
        notes.append("no scored equities")

    jkse = 50.0
    if jkse_hist is not None and not jkse_hist.empty and len(jkse_hist) >= 64:
        close = jkse_hist["Close"].dropna()
        price = float(close.iloc[-1])
        sma50 = float(close.rolling(50).mean().iloc[-1])
        ret_3m = price / float(close.iloc[-64]) - 1.0
        jkse = 50.0
        jkse += 20 if price > sma50 else -20
        jkse += _clamp(ret_3m * 200, -30, 30)
        jkse = _clamp(jkse)
        notes.append(f"JKSE {'above' if price > sma50 else 'below'} SMA50, 3M {ret_3m * 100:+.1f}%")
    else:
        notes.append("JKSE data unavailable")

    score = _clamp(0.4 * avg_score + 0.3 * breadth + 0.3 * jkse)
    return {"score": round(score, 1), "notes": notes}


def bond_class_score(macro: dict) -> dict:
    """INDOGB score from real yield level, yield momentum, and curve slope"""
    config = ALLOCATION_CONFIG
    notes = []
    score = 50.0

    real_yield = macro.get("real_yield_10y")
    if real_yield is not None:
        score += _clamp((real_yield - config["bond_neutral_real_yield"]) * 10, -25, 25)
        notes.append(f"real 10Y yield {real_yield:+.2f}%")
    else:
        notes.append("real yield unavailable")

    # Rising yields (positive Perf) = falling bond prices = bearish
    perf_3m = (macro.get("bond_momentum") or {}).get("perf_3m_pct")
    if perf_3m is not None:
        score -= _clamp(perf_3m * 1.2, -20, 20)
        notes.append(f"10Y yield {perf_3m:+.1f}% over 3M ({'headwind' if perf_3m > 0 else 'tailwind'})")

    slope = macro.get("curve_slope_10y_1y")
    if slope is not None:
        score += _clamp(slope * 5, -10, 10)
        notes.append(f"curve slope 10Y-1Y {slope:+.2f}pp")

    return {"score": round(_clamp(score), 1), "notes": notes}


def money_market_class_score(macro: dict, equity_score: float, bond_score: float) -> dict:
    """Money market score from real cash rate + defensive kicker"""
    config = ALLOCATION_CONFIG
    notes = []
    score = 50.0

    real_cash = macro.get("real_cash_rate")
    if real_cash is not None:
        score += _clamp((real_cash - config["mm_neutral_real_rate"]) * 10, -20, 20)
        notes.append(f"real cash rate {real_cash:+.2f}%")
    else:
        notes.append("real cash rate unavailable")

    # Cash becomes more attractive when both risk assets look weak
    if equity_score < 45 and bond_score < 45:
        score += 15
        notes.append("defensive kicker: equities and bonds both weak")

    return {"score": round(_clamp(score), 1), "notes": notes}


# ============================================================================
# WEIGHTS
# ============================================================================

def scores_to_weights(class_scores: dict) -> dict:
    """Map class scores to weights: benchmark + tilt, clamped to bands, normalized"""
    config = ALLOCATION_CONFIG
    raw = {}
    for asset, benchmark in config["benchmark"].items():
        tilt = (class_scores[asset] - 50.0) / 50.0 * config["max_tilt"]
        lo, hi = config["bands"][asset]
        raw[asset] = max(lo, min(hi, benchmark + tilt))

    total = sum(raw.values())
    return {asset: round(weight / total, 4) for asset, weight in raw.items()}


def compute_allocation(
    signals: List[dict],
    macro: dict,
    jkse_hist: Optional[pd.DataFrame] = None,
) -> dict:
    """Full allocation decision: class scores -> weights -> rationale"""
    equity = equity_class_score(signals, jkse_hist)
    bonds = bond_class_score(macro)
    money_market = money_market_class_score(macro, equity["score"], bonds["score"])

    class_scores = {
        "equity": equity["score"],
        "bonds": bonds["score"],
        "money_market": money_market["score"],
    }
    weights = scores_to_weights(class_scores)

    stance = max(class_scores, key=class_scores.get)
    rationale = (
        [f"Overweight tilt toward {stance.replace('_', ' ')}"]
        + [f"[equity] {n}" for n in equity["notes"]]
        + [f"[bonds] {n}" for n in bonds["notes"]]
        + [f"[money market] {n}" for n in money_market["notes"]]
    )

    return {
        "weights": weights,
        "class_scores": class_scores,
        "benchmark": ALLOCATION_CONFIG["benchmark"],
        "rationale": rationale,
    }
