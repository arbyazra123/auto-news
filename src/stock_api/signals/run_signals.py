#!/usr/bin/env python3
"""
Signal Batch Runner: daily job that computes PM signals across
IDX80 equities, government bonds, and money markets.

Steps: fetch macro -> score equities -> allocation -> persist (SQLite + JSON)
Optional: --analyze runs the Claude overlay to write signal_report.md

Designed to run after IDX close (cron) or via POST /api/signals/run.

Examples:
  # Full IDX80 run
  python run_signals.py --data-dir data

  # Quick test on a subset
  python run_signals.py --tickers BBCA,BBRI,TLKM --data-dir /tmp/sigtest

  # Full run + Claude qualitative overlay
  python run_signals.py --data-dir data --analyze
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Allow running both as a script (python signals/run_signals.py) and as a module
sys.path.insert(0, str(Path(__file__).parent.parent))

from signals.allocation import compute_allocation
from signals.equity_signals import generate_equity_signals
from signals.macro import get_macro_snapshot
from signals.store import save_run
from signals.universe import IDX80

JKSE_TICKER = "^JKSE"
DB_FILE = "signals.db"
LATEST_JSON = "signals_latest.json"
REPORT_FILE = "signal_report.md"

ANALYSIS_PROMPT = """
You are a buy-side investment analyst supporting a portfolio manager.

Below is today's output of a rules-based signal platform covering IDX80
equities, Indonesian government bonds, and money markets, plus condensed
market news. Perform the following task:
1. Review the allocation decision and the strongest BUY/SELL signals
2. Cross-check them against the news: flag any signal that the news
   contradicts (e.g. technical BUY but negative corporate action)
3. Write a professional markdown report to '{report_file}' in the current
   directory (replace it if it exists), no emoji

The report should include:
- Asset allocation view (equities vs government bonds vs money market) with rationale
- Top equity conviction ideas with entry context
- Signals to distrust (where news and technicals disagree)
- Key macro observations (yield curve, BI rate, inflation)
- Write in Bahasa Indonesia, but keep special terms in English

After writing the report, confirm it was created successfully.
"""


def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def fetch_jkse(period: str):
    """Fetch JKSE composite index history for the equity regime score"""
    try:
        import yfinance as yf
        hist = yf.download(JKSE_TICKER, period=period, interval="1d",
                           auto_adjust=True, progress=False)
        if hist is not None and not hist.empty:
            # Flatten possible MultiIndex columns from single-ticker download
            if hasattr(hist.columns, "nlevels") and hist.columns.nlevels > 1:
                hist.columns = hist.columns.get_level_values(0)
            return hist
    except Exception as e:
        log(f"WARNING: JKSE fetch failed: {e}")
    return None


def build_analysis_input(signals, allocation, macro, news_text) -> str:
    """Assemble the prompt + data payload for the Claude overlay"""
    scored = [s for s in signals if s.get("score") is not None]
    top_buys = [s for s in scored if s["signal"] == "BUY"][:15]
    sells = [s for s in scored if s["signal"] == "SELL"]

    payload = {
        "allocation": allocation,
        "macro": macro,
        "top_buy_signals": top_buys,
        "sell_signals": sells,
    }

    sections = [
        ANALYSIS_PROMPT.format(report_file=REPORT_FILE),
        "---",
        "SIGNAL PLATFORM OUTPUT (JSON):",
        json.dumps(payload, ensure_ascii=False, indent=2),
    ]
    if news_text:
        sections += ["---", "CONDENSED MARKET NEWS:", news_text]
    return "\n\n".join(sections)


def run_claude_overlay(full_input: str, data_dir: Path) -> bool:
    """Run `claude -p` on the signal output to write the qualitative report"""
    temp_input = data_dir / "claude_signal_input.txt"
    temp_input.write_text(full_input, encoding="utf-8")

    try:
        # In the Docker container this runs as root; claude requires non-root
        # for --dangerously-skip-permissions (same pattern as /api/news/analyze)
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            os.chmod(temp_input, 0o644)
            cmd = ["su", "-", "appuser", "-c",
                   f"cd {data_dir} && claude -p --dangerously-skip-permissions < {temp_input}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        else:
            result = subprocess.run(
                ["claude", "-p", "--dangerously-skip-permissions"],
                input=full_input, capture_output=True, text=True,
                timeout=300, cwd=str(data_dir),
            )

        if result.returncode != 0:
            log(f"✗ Claude overlay failed (exit {result.returncode}): {result.stderr[:500]}")
            return False
        log(f"✓ Claude overlay completed: {result.stdout.strip()[:200]}")
        return True
    except FileNotFoundError:
        log("✗ Claude overlay failed: `claude` CLI not found")
        return False
    except subprocess.TimeoutExpired:
        log("✗ Claude overlay timed out after 300s")
        return False
    finally:
        temp_input.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Run the signal batch: macro -> equity signals -> allocation -> persist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--tickers", type=str, default=None,
                        help="Comma-separated ticker subset (default: full IDX80)")
    parser.add_argument("--period", type=str, default="1y",
                        help="OHLCV history period for scoring (default: 1y)")
    parser.add_argument("--data-dir", type=str, default="data",
                        help="Directory for signals.db, JSON output, and news input (default: data)")
    parser.add_argument("--news-file", type=str, default="news_condensed.txt",
                        help="Condensed news file inside data dir (default: news_condensed.txt)")
    parser.add_argument("--notes", type=str, default="",
                        help="Free-text note stored with the run")
    parser.add_argument("--analyze", action="store_true",
                        help="Run the Claude overlay to write signal_report.md")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(data_dir / DB_FILE)

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        universe = f"CUSTOM({len(tickers)})"
    else:
        tickers = IDX80
        universe = "IDX80"

    log("=" * 60)
    log("SIGNAL BATCH STARTING")
    log("=" * 60)
    log(f"  - Universe: {universe} ({len(tickers)} tickers)")
    log(f"  - Period: {args.period}")
    log(f"  - Data dir: {data_dir}")
    log("=" * 60)

    # Step 1: Macro snapshot (yield curve, BI rate, inflation)
    log("Step 1/4: Fetching macro snapshot (INDOGB curve, BI rate, CPI)")
    macro = get_macro_snapshot()
    if macro["errors"]:
        log(f"WARNING: macro gaps: {macro['errors']}")
    log(f"  10Y {macro['yield_curve'].get('10Y')}% | BI rate {macro['bi_rate']}% "
        f"| CPI {macro['inflation_yoy']}% | real 10Y {macro['real_yield_10y']}")

    # Step 2: Equity signals
    log("Step 2/4: Scoring equities")
    news_path = data_dir / args.news_file
    news_text = news_path.read_text(encoding="utf-8") if news_path.exists() else None
    if news_text:
        log(f"  Using news context from {news_path}")

    signals = generate_equity_signals(tickers, period=args.period, news_text=news_text)
    scored = [s for s in signals if s.get("score") is not None]
    buys = sum(1 for s in scored if s["signal"] == "BUY")
    sells = sum(1 for s in scored if s["signal"] == "SELL")
    log(f"  Scored {len(scored)}/{len(signals)}: {buys} BUY, {sells} SELL, "
        f"{len(scored) - buys - sells} HOLD")

    # Step 3: Allocation
    log("Step 3/4: Computing asset allocation")
    jkse_hist = fetch_jkse(args.period)
    allocation = compute_allocation(signals, macro, jkse_hist)
    weights = allocation["weights"]
    log(f"  Weights: equity {weights['equity']:.0%} | bonds {weights['bonds']:.0%} "
        f"| money market {weights['money_market']:.0%}")

    # Step 4: Persist
    log("Step 4/4: Persisting run")
    run_id = save_run(db_path, universe, signals, allocation, macro, notes=args.notes)
    latest = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        "universe": universe,
        "allocation": allocation,
        "macro": macro,
        "signals": signals,
    }
    latest_path = data_dir / LATEST_JSON
    latest_path.write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"  Saved run {run_id} to {db_path} and {latest_path}")

    # Optional: Claude qualitative overlay
    if args.analyze:
        log("Extra: Running Claude overlay")
        full_input = build_analysis_input(signals, allocation, macro, news_text)
        run_claude_overlay(full_input, data_dir)

    log("=" * 60)
    log("SIGNAL BATCH COMPLETED SUCCESSFULLY!")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
