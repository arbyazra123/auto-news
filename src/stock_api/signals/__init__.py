"""
Signal Platform: PM buy/hold/sell signals and asset allocation
across IDX80 equities, government bonds, and money markets.

Modules:
- universe:       IDX80 constituent list
- macro:          TradingView fetchers (INDOGB yield curve, BI rate, inflation)
- equity_signals: per-ticker composite scoring -> BUY/HOLD/SELL
- allocation:     asset-class scoring -> recommended weights
- store:          SQLite persistence for signal history
- run_signals:    batch CLI runner (daily job)
"""
