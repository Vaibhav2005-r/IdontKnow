"""SQLite access for the feedback table (schema owned by ml.data.FEEDBACK_SCHEMA)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ml.data import FEEDBACK_SCHEMA


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(FEEDBACK_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_prediction(db_path: str, url: str, predicted_label: int, model_version: str) -> int:
    """Log a prediction. correct_label starts equal to predicted_label (assumed correct
    until the user flags it wrong via record_correction)."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO feedback (url, predicted_label, correct_label, model_version) "
            "VALUES (?, ?, ?, ?)",
            (url, predicted_label, predicted_label, model_version),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def record_correction(db_path: str, feedback_id: int, correct_label: int) -> bool:
    """Flip a logged prediction's correct_label. Returns False if the id doesn't exist."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE feedback SET correct_label = ? WHERE id = ?",
            (correct_label, feedback_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_feedback_row(db_path: str, feedback_id: int) -> sqlite3.Row | None:
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
    finally:
        conn.close()


def recent_feedback(db_path: str, limit: int = 20) -> list[sqlite3.Row]:
    conn = get_connection(db_path)
    try:
        return conn.execute(
            "SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()


def stats(db_path: str) -> dict:
    conn = get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM feedback").fetchone()["c"]
        corrections = conn.execute(
            "SELECT COUNT(*) AS c FROM feedback WHERE predicted_label != correct_label"
        ).fetchone()["c"]
        return {"total_predictions": total, "corrections": corrections}
    finally:
        conn.close()
