#!/usr/bin/env python3
"""
SQLite persistence for signal runs.

One row in `runs` per batch execution; equity signals, allocation, and the
macro snapshot are stored per run so the PM can track signal changes
(upgrades/downgrades) day over day. Uses stdlib sqlite3 only.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    universe    TEXT NOT NULL,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS equity_signals (
    run_id          INTEGER NOT NULL REFERENCES runs(run_id),
    ticker          TEXT NOT NULL,
    signal          TEXT NOT NULL,
    score           REAL,
    close           REAL,
    payload_json    TEXT NOT NULL,
    PRIMARY KEY (run_id, ticker)
);

CREATE TABLE IF NOT EXISTS allocations (
    run_id          INTEGER PRIMARY KEY REFERENCES runs(run_id),
    equity_weight   REAL NOT NULL,
    bond_weight     REAL NOT NULL,
    mm_weight       REAL NOT NULL,
    payload_json    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS macro_snapshots (
    run_id          INTEGER PRIMARY KEY REFERENCES runs(run_id),
    payload_json    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_equity_signals_ticker ON equity_signals(ticker);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_run(
    db_path: str,
    universe: str,
    signals: List[dict],
    allocation: dict,
    macro: dict,
    notes: str = "",
) -> int:
    """Persist a complete batch run; returns the new run_id"""
    now = datetime.now()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO runs (run_date, created_at, universe, notes) VALUES (?, ?, ?, ?)",
            (now.strftime("%Y-%m-%d"), now.isoformat(), universe, notes),
        )
        run_id = cursor.lastrowid

        conn.executemany(
            "INSERT INTO equity_signals (run_id, ticker, signal, score, close, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (run_id, s["ticker"], s["signal"], s.get("score"), s.get("close"),
                 json.dumps(s, ensure_ascii=False))
                for s in signals
            ],
        )

        weights = allocation["weights"]
        conn.execute(
            "INSERT INTO allocations (run_id, equity_weight, bond_weight, mm_weight, payload_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, weights["equity"], weights["bonds"], weights["money_market"],
             json.dumps(allocation, ensure_ascii=False)),
        )

        conn.execute(
            "INSERT INTO macro_snapshots (run_id, payload_json) VALUES (?, ?)",
            (run_id, json.dumps(macro, ensure_ascii=False)),
        )

    return run_id


def get_latest_run(db_path: str) -> Optional[dict]:
    """Metadata of the most recent run, or None if no runs exist"""
    if not Path(db_path).exists():
        return None
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def get_signals(
    db_path: str,
    run_id: Optional[int] = None,
    signal: Optional[str] = None,
    min_score: Optional[float] = None,
) -> List[dict]:
    """Equity signals for a run (default: latest), optionally filtered"""
    with _connect(db_path) as conn:
        if run_id is None:
            latest = conn.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()
            if latest is None:
                return []
            run_id = latest["run_id"]

        query = "SELECT payload_json FROM equity_signals WHERE run_id = ?"
        params = [run_id]
        if signal:
            query += " AND signal = ?"
            params.append(signal.upper())
        if min_score is not None:
            query += " AND score >= ?"
            params.append(min_score)
        query += " ORDER BY score DESC"

        return [json.loads(row["payload_json"]) for row in conn.execute(query, params)]


def get_allocation(db_path: str, run_id: Optional[int] = None) -> Optional[dict]:
    """Allocation decision for a run (default: latest)"""
    with _connect(db_path) as conn:
        if run_id is None:
            row = conn.execute(
                "SELECT payload_json FROM allocations ORDER BY run_id DESC LIMIT 1"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT payload_json FROM allocations WHERE run_id = ?", (run_id,)
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None


def get_macro(db_path: str, run_id: Optional[int] = None) -> Optional[dict]:
    """Macro snapshot for a run (default: latest)"""
    with _connect(db_path) as conn:
        if run_id is None:
            row = conn.execute(
                "SELECT payload_json FROM macro_snapshots ORDER BY run_id DESC LIMIT 1"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT payload_json FROM macro_snapshots WHERE run_id = ?", (run_id,)
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None


def get_signal_changes(db_path: str) -> dict:
    """Upgrades/downgrades between the two most recent runs"""
    with _connect(db_path) as conn:
        runs = conn.execute("SELECT run_id, run_date FROM runs ORDER BY run_id DESC LIMIT 2").fetchall()
        if len(runs) < 2:
            return {"changes": [], "message": "Need at least 2 runs to compare"}

        current, previous = runs[0], runs[1]
        rows = conn.execute(
            """
            SELECT c.ticker, p.signal AS prev_signal, c.signal AS curr_signal,
                   p.score AS prev_score, c.score AS curr_score
            FROM equity_signals c
            JOIN equity_signals p ON p.ticker = c.ticker AND p.run_id = ?
            WHERE c.run_id = ? AND c.signal != p.signal
            ORDER BY c.score DESC
            """,
            (previous["run_id"], current["run_id"]),
        ).fetchall()

        rank = {"SELL": 0, "HOLD": 1, "BUY": 2}
        changes = []
        for row in rows:
            change = dict(row)
            prev, curr = rank.get(row["prev_signal"]), rank.get(row["curr_signal"])
            if prev is not None and curr is not None:
                change["direction"] = "UPGRADE" if curr > prev else "DOWNGRADE"
            else:
                change["direction"] = "DATA_CHANGE"
            changes.append(change)

        return {
            "current_run": dict(current),
            "previous_run": dict(previous),
            "changes": changes,
        }


def get_ticker_history(db_path: str, ticker: str, limit: int = 30) -> List[dict]:
    """Signal history for one ticker across runs (newest first)"""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT r.run_date, e.signal, e.score, e.close
            FROM equity_signals e
            JOIN runs r ON r.run_id = e.run_id
            WHERE e.ticker = ?
            ORDER BY e.run_id DESC LIMIT ?
            """,
            (ticker.upper().replace(".JK", ""), limit),
        ).fetchall()
        return [dict(row) for row in rows]
