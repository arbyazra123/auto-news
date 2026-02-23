#!/usr/bin/env python3
"""
MCP Server wrapper for Indonesian Stock Analysis API (News tools only).

Designed to run INSIDE the Docker container so it shares the same
data volume (/app/data) as the FastAPI server.

Claude config (add to ~/.claude.json mcpServers):
  "stock-news": {
    "type": "stdio",
    "command": "docker",
    "args": ["exec", "-i", "idx-stock-api", "python3", "/app/mcp_server.py"]
  }

The server calls http://localhost:13052 (FastAPI running in the same container).
env: STOCK_API_URL to override the base URL if needed.
"""

import os
import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.getenv("STOCK_API_URL", "http://localhost:13052")

mcp = FastMCP("Indonesian Stock API")


def _post(path: str, body: dict) -> dict:
    try:
        resp = httpx.post(f"{BASE_URL}{path}", json=body, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        return {"error": f"Cannot connect to stock API at {BASE_URL}. Make sure the server is running."}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"error": str(e)}


def _get(path: str, params: dict = None) -> dict | str:
    try:
        resp = httpx.get(f"{BASE_URL}{path}", params=params, timeout=120)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "text/plain" in ct:
            return resp.text
        return resp.json()
    except httpx.ConnectError:
        return {"error": f"Cannot connect to stock API at {BASE_URL}. Make sure the server is running."}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# STOCK DATA TOOLS
# ============================================================================

# @mcp.tool()
# def get_stock_price(symbol: str) -> dict:
#     """
#     Get current/latest price and basic info for an Indonesian stock (IDX).
#     Symbol should be the ticker without .JK, e.g. BBCA, BBRI, TLKM.
#     Returns: price, change, change_percent, volume, high, low, open, market_cap.
#     """
#     return _post("/api/stock/price", {"symbol": symbol})


# @mcp.tool()
# def get_historical_data(symbol: str, period: str = "3mo") -> dict:
#     """
#     Get historical OHLCV (Open, High, Low, Close, Volume) data for an Indonesian stock.
#     Symbol: ticker without .JK (e.g. BBCA).
#     Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max.
#     """
#     return _post("/api/stock/history", {"symbol": symbol, "period": period})


# @mcp.tool()
# def get_technical_indicators(symbol: str, period: str = "6mo") -> dict:
#     """
#     Calculate technical indicators for an Indonesian stock.
#     Returns: RSI(14), MACD, SMA20, SMA50, EMA12, Bollinger Bands.
#     Symbol: ticker without .JK (e.g. BBCA). Period: 3mo, 6mo, 1y.
#     """
#     return _post("/api/stock/technicals", {"symbol": symbol, "period": period})


# @mcp.tool()
# def get_bandarmology(symbol: str, period: str = "6mo") -> dict:
#     """
#     Bandarmology / smart-money analysis for an Indonesian stock.
#     Uses OBV, ADL, VPT, MFI, ATR and Wyckoff-style phases.
#     Returns: score (0-100), phase (ACCUMULATION/MARKUP/DISTRIBUTION/MARKDOWN),
#     signals, setup recommendation, and key price levels.
#     Symbol: ticker without .JK (e.g. BBCA). Period: 3mo, 6mo, 1y.
#     """
#     return _post("/api/stock/bandarmology", {"symbol": symbol, "period": period})


# @mcp.tool()
# def get_fundamentals(symbol: str) -> dict:
#     """
#     Get fundamental data for an Indonesian stock.
#     Returns: market cap, P/E ratio, P/B ratio, EPS, dividend yield,
#     revenue, profit margin, ROE, debt-to-equity, current ratio, beta.
#     Symbol: ticker without .JK (e.g. BBCA).
#     """
#     return _post("/api/stock/fundamentals", {"symbol": symbol})


# @mcp.tool()
# def get_mandiri_report(symbol: str, period: str = "6mo") -> str:
#     """
#     Generate a Mandiri Sekuritas-style analysis report for an Indonesian stock.
#     Includes technicals, bandarmology, entry/exit levels, and trading setup.
#     Returns a formatted text report.
#     Symbol: ticker without .JK (e.g. BBCA). Period: 3mo, 6mo, 1y.
#     """
#     result = _post("/api/stock/mandiri-report", {"symbol": symbol, "period": period})
#     if isinstance(result, dict):
#         return result.get("report", str(result))
#     return str(result)


# # ============================================================================
# # MARKET CONTEXT TOOLS
# # ============================================================================

# @mcp.tool()
# def check_global_markets() -> dict:
#     """
#     Check global market sentiment that impacts IDX (Indonesian Stock Exchange).
#     Returns: S&P500, Nikkei, commodity sentiment and overall market sentiment (POSITIVE/NEUTRAL/NEGATIVE).
#     """
#     return _post("/api/market/global", {})


# @mcp.tool()
# def get_trading_time_context() -> dict:
#     """
#     Get current WIB (Jakarta) time and determine trading session context.
#     Returns: current session (PRE_OPEN/SESSION_1/SESSION_2/BREAK/AFTER_HOURS),
#     recommended strategy (PREOPEN/BPJS/BSJP), and whether trading is active.
#     """
#     return _post("/api/market/time-context", {})


# @mcp.tool()
# def get_stock_list(stock_index: str = "BOTH") -> dict:
#     """
#     Get the list of Indonesian stocks by index.
#     stock_index: LQ45, IDX30, or BOTH (default).
#     Returns the list of ticker symbols for the selected index.
#     """
#     return _post("/api/market/stock-list", {"stock_index": stock_index})


# # ============================================================================
# # SCREENING TOOLS
# # ============================================================================

# @mcp.tool()
# def screen_preopen_setups(
#     stock_index: str = "BOTH",
#     limit: int = 10,
#     min_score: int = 70,
#     min_avg_volume: int = 1000000,
#     enable_bandarmology: bool = True
# ) -> dict:
#     """
#     Screen for PRE-OPEN trading setups (analyzed overnight, execute at 08:45-08:58 WIB).
#     Looks for stocks that closed strong (near HOD) with accumulation signals.
#     stock_index: LQ45, IDX30, or BOTH. limit: max results. min_score: 0-100.
#     """
#     return _post("/api/screen/preopen", {
#         "stock_index": stock_index,
#         "limit": limit,
#         "min_score": min_score,
#         "min_avg_volume": min_avg_volume,
#         "enable_bandarmology": enable_bandarmology
#     })


# @mcp.tool()
# def screen_bpjs_setups(
#     stock_index: str = "BOTH",
#     limit: int = 10,
#     min_score: int = 65,
#     min_avg_volume: int = 1000000,
#     enable_bandarmology: bool = True
# ) -> dict:
#     """
#     Screen for BPJS (Beli Pagi Jual Sore) - intraday buy morning sell afternoon setups.
#     Looks for MACD bullish crossover + not overbought RSI + volume spike.
#     Must exit before 15:49 WIB. stock_index: LQ45, IDX30, or BOTH.
#     """
#     return _post("/api/screen/bpjs", {
#         "stock_index": stock_index,
#         "limit": limit,
#         "min_score": min_score,
#         "min_avg_volume": min_avg_volume,
#         "enable_bandarmology": enable_bandarmology
#     })


# @mcp.tool()
# def screen_bsjp_setups(
#     stock_index: str = "BOTH",
#     limit: int = 10,
#     min_score: int = 60,
#     min_avg_volume: int = 1000000,
#     enable_bandarmology: bool = False
# ) -> dict:
#     """
#     Screen for BSJP (Beli Sore Jual Pagi) - buy afternoon sell next morning setups.
#     Looks for accumulation/compression with strong close near HOD for gap-up overnight.
#     Exit window: 09:00-11:30 WIB next day. stock_index: LQ45, IDX30, or BOTH.
#     """
#     return _post("/api/screen/bsjp", {
#         "stock_index": stock_index,
#         "limit": limit,
#         "min_score": min_score,
#         "min_avg_volume": min_avg_volume,
#         "enable_bandarmology": enable_bandarmology
#     })


# @mcp.tool()
# def screen_day_trade_setups(
#     stock_index: Optional[str] = None,
#     limit: int = 10,
#     mode: str = "mandiri"
# ) -> dict:
#     """
#     Screen for day trade opportunities using Mandiri Sekuritas-style criteria.
#     Returns formatted table with recommendations, entry/target/stop levels.
#     mode: 'mandiri' (lenient) or 'strict'. stock_index: LQ45, IDX30, or BOTH.
#     """
#     return _post("/api/screen/day-trade", {
#         "stock_index": stock_index,
#         "limit": limit,
#         "mode": mode
#     })


# ============================================================================
# NEWS PIPELINE TOOLS
# ============================================================================

@mcp.tool()
def get_news_status() -> dict:
    """
    Check the current status of the news pipeline.
    Returns: is_running, last_run timestamp, last_status (success/failed), last_error.
    """
    return _get("/api/news/status")


@mcp.tool()
def run_news_pipeline_async(
    max_items: int = 100,
    query: str = "today's indonesia stock market movements, price changes, trading analysis, and financial news",
    top_k: int = 30,
    days_back: int = 2,
    max_chars: int = 2000,
    output: str = "news_condensed.txt",
    skip_scrape: bool = False,
    skip_index: bool = False
) -> dict:
    """
    Start the news pipeline in the background (non-blocking).
    Scrapes Indonesian financial news, indexes with Milvus, and creates condensed report.
    Check progress with get_news_status(), read result with read_news_report().
    max_items: articles to scrape. top_k: top relevant articles. days_back: lookback days.
    """
    return _post("/api/news/get", {
        "max_items": max_items,
        "query": query,
        "top_k": top_k,
        "days_back": days_back,
        "max_chars": max_chars,
        "output": output,
        "skip_scrape": skip_scrape,
        "skip_index": skip_index
    })


@mcp.tool()
def run_news_pipeline_sync(
    max_items: int = 100,
    query: str = "today's indonesia stock market movements, price changes, trading analysis, and financial news",
    top_k: int = 30,
    days_back: int = 2,
    max_chars: int = 2000,
    output: str = "news_condensed.txt",
    skip_scrape: bool = False,
    skip_index: bool = False
) -> dict:
    """
    Run the news pipeline synchronously (blocking - waits for completion).
    Scrapes Indonesian financial news, indexes with Milvus, and creates condensed report.
    Use run_news_pipeline_async() for non-blocking version.
    max_items: articles to scrape. top_k: top relevant articles. days_back: lookback days.
    """
    return _post("/api/news/get/sync", {
        "max_items": max_items,
        "query": query,
        "top_k": top_k,
        "days_back": days_back,
        "max_chars": max_chars,
        "output": output,
        "skip_scrape": skip_scrape,
        "skip_index": skip_index
    })


@mcp.tool()
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


@mcp.tool()
def read_news_report(file: str = "news_condensed.txt") -> str:
    """
    Read the condensed news report generated by the news pipeline.
    Returns the report content as plain text.
    file: output filename (default: news_condensed.txt).
    Run run_news_pipeline_async() or run_news_pipeline_sync() first if file not found.
    """
    result = _get("/api/news/read", {"file": file})
    if isinstance(result, str):
        return result
    return str(result)


# @mcp.tool()
# def analyze_news_with_claude() -> str:
#     """
#     Read the condensed news from /app/data and analyze it using `claude -p` CLI.
#     Uses the host's Claude credentials mounted at /root/.claude (read-only).
#     prompt: analysis instruction prepended before the news content.
#     file: news file in /app/data/ (default: news_condensed.txt).
#     """
#     import subprocess
#     from pathlib import Path

#     prompt: str = """
# You are a financial analyst.

# Please perform the following task:
# 1. Analyze the financial news articles focusing on:
#    - Price movements and catalysts
#    - Market sentiment
#    - Key stock tickers mentioned
#    - Dominant themes
# 2. Generate a comprehensive markdown report
# 3. Write the report to 'daily_report.md' in the current directory, make sure it has no emoji, treat as professional report
# 4. If 'daily_report.md' already exists, just replace (delete and write a new report)

# The report should include:
# - Market overview section
# - Most mentioned stocks with analysis
# - Top 3 actionable recommendations
# - Honorable article insights with sentiment
# - Be concise and data-focused
# - Important - write in Bahasa Indonesia, but for special terms, use English

# After writing the report, confirm it was created successfully.
# """

#     file: str = "news_condensed.txt"

#     news_path = Path(f"/app/data/{file}")
#     if not news_path.exists():
#         return f"ERROR: {file} not found in /app/data. Run the news pipeline first."

#     content = news_path.read_text(encoding="utf-8")
#     full_input = f"{prompt}\n\n---\n\n{content}"

#     try:
#         result = subprocess.run(
#             ["runuser", "-u", "appuser", "--", "claude", "-p", "--dangerously-skip-permissions"],
#             input=full_input,
#             capture_output=True,
#             text=True,
#             timeout=300,
#             cwd="/app/data",
#             env={**os.environ, "HOME": "/root"},
#         )
#         if result.returncode != 0:
#             return f"ERROR (exit {result.returncode}):\n{result.stderr}"
#         return result.stdout.strip()
#     except FileNotFoundError:
#         return "ERROR: `claude` CLI not found in container. Rebuild the Docker image."
#     except subprocess.TimeoutExpired:
#         return "ERROR: claude -p timed out after 300s."
#     except Exception as e:
#         return f"ERROR: {e}"


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
