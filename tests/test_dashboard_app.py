"""Smoke-test dashboard/app.py by actually running it (streamlit's AppTest),
not just its pure helpers in dashboard/data.py -- this is what catches bugs
like a forgotten top-level import that only blows up once real data (a
promoted model, feedback rows) reaches the code path that uses it.
"""
import json
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from ml.data import FEEDBACK_SCHEMA


@pytest.fixture
def dashboard_env(tmp_path, monkeypatch):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({
        "live_version": "1.0",
        "models": [{
            "version": "1.0",
            "path": "models/phishguard_v1.0.joblib",
            "model_type": "rf",
            "accuracy": 0.89,
            "trained_at": "2026-01-01T00:00:00+00:00",
            "data_fingerprint": "abc123",
            "n_samples": 11429,
            "promoted": True,
        }],
    }))

    history_path = tmp_path / "run_history.jsonl"
    history_path.write_text(json.dumps({
        "timestamp": "2026-01-01T00:00:00+00:00",
        "status": "promoted",
        "candidate_accuracy": 0.89,
    }) + "\n")

    db_path = tmp_path / "feedback.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(FEEDBACK_SCHEMA)
    conn.execute(
        "INSERT INTO feedback (url, predicted_label, correct_label, model_version) "
        "VALUES (?, ?, ?, ?)",
        ("http://example.com", 1, 0, "1.0"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("MODEL_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv("RUN_HISTORY_PATH", str(history_path))
    monkeypatch.setenv("FEEDBACK_DB_PATH", str(db_path))


def test_dashboard_runs_without_exception_with_data(dashboard_env):
    at = AppTest.from_file("dashboard/app.py", default_timeout=15)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]


def test_dashboard_runs_without_exception_when_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_REGISTRY_PATH", str(tmp_path / "nope.json"))
    monkeypatch.setenv("RUN_HISTORY_PATH", str(tmp_path / "nope.jsonl"))
    monkeypatch.setenv("FEEDBACK_DB_PATH", str(tmp_path / "nope.db"))

    at = AppTest.from_file("dashboard/app.py", default_timeout=15)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
