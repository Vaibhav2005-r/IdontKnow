import sqlite3

import pandas as pd
import pytest

from ml.data import (
    FEEDBACK_SCHEMA,
    fingerprint,
    init_feedback_db,
    load_dataset,
    load_feedback,
    merge_feedback,
)


@pytest.fixture
def sample_csv(tmp_path):
    path = tmp_path / "dataset.csv"
    pd.DataFrame({
        "url": ["http://example.com", "http://phish.tk/login", "http://example.com"],
        "status": ["legitimate", "phishing", "legitimate"],
    }).to_csv(path, index=False)
    return path


def test_load_dataset_normalizes_columns_and_labels(sample_csv):
    df = load_dataset(sample_csv)
    assert list(df.columns) == ["url", "label"]
    assert len(df) == 2  # duplicate URL dropped
    labels = dict(zip(df["url"], df["label"]))
    assert labels["http://example.com"] == 0
    assert labels["http://phish.tk/login"] == 1


def test_load_dataset_invert_labels(sample_csv):
    df = load_dataset(sample_csv, invert_labels=True)
    labels = dict(zip(df["url"], df["label"]))
    assert labels["http://example.com"] == 1
    assert labels["http://phish.tk/login"] == 0


def test_load_dataset_numeric_labels(tmp_path):
    path = tmp_path / "numeric.csv"
    pd.DataFrame({"URL": ["http://a.com", "http://b.com"], "label": [0, 1]}).to_csv(path, index=False)
    df = load_dataset(path)
    assert set(df["label"]) == {0, 1}


def test_load_feedback_missing_file_returns_empty(tmp_path):
    df = load_feedback(tmp_path / "nope.db")
    assert df.empty
    assert list(df.columns) == ["url", "label"]


def test_load_feedback_from_sqlite(tmp_path):
    db_path = tmp_path / "feedback.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(FEEDBACK_SCHEMA)
    conn.execute(
        "INSERT INTO feedback (url, predicted_label, correct_label, model_version) "
        "VALUES (?, ?, ?, ?)",
        ("http://phish.tk/login", 0, 1, "1.0"),
    )
    conn.commit()
    conn.close()

    df = load_feedback(db_path)
    assert len(df) == 1
    assert df.iloc[0]["url"] == "http://phish.tk/login"
    assert df.iloc[0]["label"] == 1


def test_init_feedback_db_creates_table(tmp_path):
    db_path = tmp_path / "sub" / "feedback.db"
    init_feedback_db(db_path)
    conn = sqlite3.connect(db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()
    assert ("feedback",) in tables


def test_merge_feedback_user_label_wins():
    dataset = pd.DataFrame({"url": ["http://a.com", "http://b.com"], "label": [0, 0]})
    feedback = pd.DataFrame({"url": ["http://a.com"], "label": [1]})
    merged = merge_feedback(dataset, feedback)
    labels = dict(zip(merged["url"], merged["label"]))
    assert labels["http://a.com"] == 1
    assert labels["http://b.com"] == 0


def test_merge_feedback_empty_returns_dataset():
    dataset = pd.DataFrame({"url": ["http://a.com"], "label": [0]})
    merged = merge_feedback(dataset, pd.DataFrame(columns=["url", "label"]))
    assert len(merged) == 1


def test_fingerprint_stable_and_order_independent():
    df1 = pd.DataFrame({"url": ["http://a.com", "http://b.com"], "label": [0, 1]})
    df2 = pd.DataFrame({"url": ["http://b.com", "http://a.com"], "label": [1, 0]})
    assert fingerprint(df1) == fingerprint(df2)


def test_fingerprint_changes_with_data():
    df1 = pd.DataFrame({"url": ["http://a.com"], "label": [0]})
    df2 = pd.DataFrame({"url": ["http://a.com"], "label": [1]})
    assert fingerprint(df1) != fingerprint(df2)
