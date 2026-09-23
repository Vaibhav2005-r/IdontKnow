"""Dataset loading, feedback ingestion, and merge logic.

Label convention everywhere in this project: 1 = phishing, 0 = safe.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pandas as pd

FEEDBACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    predicted_label INTEGER NOT NULL CHECK (predicted_label IN (0, 1)),
    correct_label INTEGER NOT NULL CHECK (correct_label IN (0, 1)),
    model_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_URL_COLUMN_CANDIDATES = ("url", "URL", "urls", "link", "website")
_LABEL_COLUMN_CANDIDATES = ("label", "status", "type", "Label", "Status", "class", "result")

_PHISHING_STRINGS = {"phishing", "bad", "malicious", "1", "yes", "true"}
_SAFE_STRINGS = {"legitimate", "safe", "good", "benign", "0", "no", "false"}


def _find_column(columns: list[str], candidates: tuple[str, ...]) -> str:
    lower_map = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    raise ValueError(f"None of {candidates} found in columns {columns}")


def _normalize_label(value, invert: bool) -> int:
    if isinstance(value, (int, float)):
        label = int(value)
    else:
        text = str(value).strip().lower()
        if text in _PHISHING_STRINGS:
            label = 1
        elif text in _SAFE_STRINGS:
            label = 0
        else:
            raise ValueError(f"Unrecognized label value: {value!r}")
    if invert:
        label = 1 - label
    if label not in (0, 1):
        raise ValueError(f"Label out of range after normalization: {label!r}")
    return label


def load_dataset(path: str | Path, invert_labels: bool = False) -> pd.DataFrame:
    """Load any CSV with a URL column and a label column -> DataFrame[url, label]."""
    raw = pd.read_csv(path)
    url_col = _find_column(list(raw.columns), _URL_COLUMN_CANDIDATES)
    label_col = _find_column(list(raw.columns), _LABEL_COLUMN_CANDIDATES)

    df = pd.DataFrame({
        "url": raw[url_col].astype(str).str.strip(),
        "label": raw[label_col].apply(lambda v: _normalize_label(v, invert_labels)),
    })
    df = df[df["url"].str.len() > 0].drop_duplicates(subset="url").reset_index(drop=True)
    return df


def load_feedback(path: str | Path) -> pd.DataFrame:
    """Read the app's SQLite feedback DB (or a CSV fallback) -> DataFrame[url, label]."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=["url", "label"])

    if path.suffix == ".csv":
        raw = pd.read_csv(path)
        return pd.DataFrame({
            "url": raw["url"].astype(str).str.strip(),
            "label": raw["correct_label"].astype(int),
        })

    conn = sqlite3.connect(str(path))
    try:
        raw = pd.read_sql_query("SELECT url, correct_label FROM feedback", conn)
    except (sqlite3.OperationalError, pd.errors.DatabaseError):
        return pd.DataFrame(columns=["url", "label"])
    finally:
        conn.close()

    if raw.empty:
        return pd.DataFrame(columns=["url", "label"])

    raw["url"] = raw["url"].astype(str).str.strip()
    dedup = raw.drop_duplicates(subset="url", keep="last")
    return pd.DataFrame({"url": dedup["url"], "label": dedup["correct_label"].astype(int)})


def merge_feedback(dataset: pd.DataFrame, feedback: pd.DataFrame) -> pd.DataFrame:
    """Merge feedback into the base dataset. The user's label wins on duplicate URLs."""
    if feedback.empty:
        return dataset.reset_index(drop=True)

    combined = pd.concat([dataset, feedback], ignore_index=True)
    merged = combined.drop_duplicates(subset="url", keep="last").reset_index(drop=True)
    return merged


def fingerprint(df: pd.DataFrame) -> str:
    """Stable hash of the training data, used to tell model versions apart."""
    payload = "\n".join(f"{row.url}\t{row.label}" for row in df.sort_values("url").itertuples())
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def init_feedback_db(path: str | Path) -> None:
    """Create the feedback table if it does not already exist."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(FEEDBACK_SCHEMA)
        conn.commit()
    finally:
        conn.close()
