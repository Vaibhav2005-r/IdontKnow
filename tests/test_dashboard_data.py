import json
import sqlite3

from dashboard.data import load_feedback, load_registry, load_run_history
from ml.data import FEEDBACK_SCHEMA


def test_load_registry_missing_file_returns_empty_shape(tmp_path):
    registry = load_registry(tmp_path / "nope.json")
    assert registry == {"live_version": None, "models": []}


def test_load_registry_reads_existing_file(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"live_version": "1.0", "models": [{"version": "1.0"}]}))
    registry = load_registry(path)
    assert registry["live_version"] == "1.0"
    assert len(registry["models"]) == 1


def test_load_run_history_missing_file_returns_empty_df(tmp_path):
    df = load_run_history(tmp_path / "nope.jsonl")
    assert df.empty


def test_load_run_history_parses_jsonl_and_sorts(tmp_path):
    path = tmp_path / "history.jsonl"
    rows = [
        {"timestamp": "2024-01-02T00:00:00+00:00", "status": "promoted", "candidate_accuracy": 0.9},
        {"timestamp": "2024-01-01T00:00:00+00:00", "status": "rejected", "candidate_accuracy": 0.8},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows))
    df = load_run_history(path)
    assert len(df) == 2
    assert df.iloc[0]["status"] == "rejected"  # earlier timestamp sorts first


def test_load_feedback_missing_db_returns_empty_df(tmp_path):
    df = load_feedback(tmp_path / "nope.db")
    assert df.empty


def test_load_feedback_reads_rows_desc(tmp_path):
    db_path = tmp_path / "feedback.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(FEEDBACK_SCHEMA)
    conn.execute(
        "INSERT INTO feedback (url, predicted_label, correct_label, model_version) VALUES (?, ?, ?, ?)",
        ("http://a.com", 1, 0, "1.0"),
    )
    conn.execute(
        "INSERT INTO feedback (url, predicted_label, correct_label, model_version) VALUES (?, ?, ?, ?)",
        ("http://b.com", 0, 0, "1.0"),
    )
    conn.commit()
    conn.close()

    df = load_feedback(db_path)
    assert len(df) == 2
    assert df.iloc[0]["url"] == "http://b.com"  # most recent id first
