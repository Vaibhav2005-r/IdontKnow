"""Pure data-loading for the dashboard -- no Streamlit calls, so it's testable
without a running `streamlit run` script context."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd


def load_registry(registry_path: str | Path) -> dict:
    registry_path = Path(registry_path)
    if not registry_path.exists():
        return {"live_version": None, "models": []}
    return json.loads(registry_path.read_text())


def load_run_history(history_path: str | Path) -> pd.DataFrame:
    history_path = Path(history_path)
    if not history_path.exists():
        return pd.DataFrame()
    lines = [ln for ln in history_path.read_text().splitlines() if ln.strip()]
    if not lines:
        return pd.DataFrame()
    df = pd.DataFrame([json.loads(ln) for ln in lines])
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp")


def load_feedback(db_path: str | Path) -> pd.DataFrame:
    db_path = Path(db_path)
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query("SELECT * FROM feedback ORDER BY id DESC", conn)
    except (sqlite3.OperationalError, pd.errors.DatabaseError):
        return pd.DataFrame()
    finally:
        conn.close()
