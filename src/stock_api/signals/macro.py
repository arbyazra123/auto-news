#!/usr/bin/env python3
"""
Macro data fetchers for the signal platform.

Sources (TradingView scanner API, no auth required):
- INDOGB yield curve:  TVC:ID03MY ... TVC:ID30Y
  (same data as https://www.tradingview.com/symbols/TVC-ID10Y/yield-curve/)
- BI policy rate:      ECONOMICS:IDINTR
- Inflation YoY:       ECONOMICS:IDIRYY

All fetchers degrade gracefully: on network/parse failure they return None
values and record the error, so a batch run never dies on macro data.
"""
import logging
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger("idx-stock-api")

TV_SCANNER_URL = "https://scanner.tradingview.com/symbol"
TV_HEADERS = {"User-Agent": "Mozilla/5.0 (auto-news signal platform)"}
TV_TIMEOUT = 15

# Tenors available for Indonesia on TradingView (no 2Y / 7Y quotes)
YIELD_CURVE_SYMBOLS = {
    "3M": "TVC:ID03MY",
    "6M": "TVC:ID06MY",
    "1Y": "TVC:ID01Y",
    "3Y": "TVC:ID03Y",
    "5Y": "TVC:ID05Y",
    "10Y": "TVC:ID10Y",
    "15Y": "TVC:ID15Y",
    "20Y": "TVC:ID20Y",
    "25Y": "TVC:ID25Y",
    "30Y": "TVC:ID30Y",
}

ECONOMICS_SYMBOLS = {
    "bi_rate": "ECONOMICS:IDINTR",
    "inflation_yoy": "ECONOMICS:IDIRYY",
}


def fetch_tv_fields(symbol: str, fields: str = "close") -> Optional[dict]:
    """Fetch fields for one symbol from the TradingView scanner API"""
    try:
        resp = requests.get(
            TV_SCANNER_URL,
            params={"symbol": symbol, "fields": fields, "no_404": "true"},
            headers=TV_HEADERS,
            timeout=TV_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return None
        return data
    except Exception as e:
        logger.warning(f"TradingView fetch failed for {symbol}: {e}")
        return None


def get_yield_curve() -> dict:
    """Fetch the INDOGB yield curve. Returns {tenor: yield_pct or None}"""
    curve = {}
    for tenor, symbol in YIELD_CURVE_SYMBOLS.items():
        data = fetch_tv_fields(symbol, "close")
        curve[tenor] = data.get("close") if data else None
    return curve


def get_macro_snapshot() -> dict:
    """
    Fetch the full macro picture used by the allocation module:
    - yield curve + 10Y momentum (Perf fields = % change of the yield)
    - BI policy rate, inflation YoY
    - derived: real 10Y yield, real cash rate, curve slope 10Y-1Y
    """
    errors = []

    curve = get_yield_curve()
    if all(v is None for v in curve.values()):
        errors.append("yield curve unavailable")

    # 10Y momentum: positive Perf = yields rising = bearish for bonds
    id10y = fetch_tv_fields(YIELD_CURVE_SYMBOLS["10Y"], "close,Perf.W,Perf.1M,Perf.3M")
    bond_momentum = {
        "perf_1w_pct": id10y.get("Perf.W") if id10y else None,
        "perf_1m_pct": id10y.get("Perf.1M") if id10y else None,
        "perf_3m_pct": id10y.get("Perf.3M") if id10y else None,
    }

    econ = {}
    for name, symbol in ECONOMICS_SYMBOLS.items():
        data = fetch_tv_fields(symbol, "close")
        econ[name] = data.get("close") if data else None
        if econ[name] is None:
            errors.append(f"{name} unavailable")

    yield_10y = curve.get("10Y")
    yield_1y = curve.get("1Y")
    bi_rate = econ.get("bi_rate")
    inflation = econ.get("inflation_yoy")

    real_yield_10y = (yield_10y - inflation) if yield_10y is not None and inflation is not None else None
    real_cash_rate = (bi_rate - inflation) if bi_rate is not None and inflation is not None else None
    curve_slope = (yield_10y - yield_1y) if yield_10y is not None and yield_1y is not None else None

    return {
        "fetched_at": datetime.now().isoformat(),
        "yield_curve": curve,
        "bond_momentum": bond_momentum,
        "bi_rate": bi_rate,
        "inflation_yoy": inflation,
        "real_yield_10y": real_yield_10y,
        "real_cash_rate": real_cash_rate,
        "curve_slope_10y_1y": curve_slope,
        "errors": errors,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_macro_snapshot(), indent=2))
