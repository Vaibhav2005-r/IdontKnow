import json
from pathlib import Path

import pytest

from ml import train
from ml.sample_data import generate_sample_dataset


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_path = tmp_path / "data.csv"
    generate_sample_dataset(n=200, seed=1).to_csv(data_path, index=False)
    return tmp_path, data_path


def test_first_run_promotes_v1_0(workdir):
    _, data_path = workdir
    code = train.main(["--data", str(data_path), "--min-accuracy", "0.0"])
    assert code == 0

    registry = json.loads(Path("models/registry.json").read_text())
    assert registry["live_version"] == "1.0"
    assert Path("models/phishguard_v1.0.joblib").exists()

    last_run = json.loads(Path("artifacts/last_run.json").read_text())
    assert last_run["status"] == "promoted"
    assert last_run["version"] == "1.0"


def test_rejected_run_does_not_bump_version(workdir):
    _, data_path = workdir
    train.main(["--data", str(data_path), "--min-accuracy", "0.0"])

    code = train.main(["--data", str(data_path), "--min-accuracy", "1.1"])
    assert code == 2

    registry = json.loads(Path("models/registry.json").read_text())
    assert registry["live_version"] == "1.0"
    assert len(registry["models"]) == 1

    last_run = json.loads(Path("artifacts/last_run.json").read_text())
    assert last_run["status"] == "rejected"


def test_promoted_run_bumps_version(workdir):
    _, data_path = workdir
    train.main(["--data", str(data_path), "--min-accuracy", "0.0"])
    code = train.main(["--data", str(data_path), "--min-accuracy", "0.0"])
    assert code == 0

    registry = json.loads(Path("models/registry.json").read_text())
    assert registry["live_version"] == "1.1"
    assert len(registry["models"]) == 2


def test_error_on_missing_data_file(workdir):
    tmp_path, _ = workdir
    code = train.main(["--data", str(tmp_path / "does_not_exist.csv")])
    assert code == 1

    last_run = json.loads(Path("artifacts/last_run.json").read_text())
    assert last_run["status"] == "error"


def test_gate_compares_against_live_model_on_same_split(workdir):
    _, data_path = workdir
    train.main(["--data", str(data_path), "--min-accuracy", "0.0"])
    code = train.main(["--data", str(data_path)])
    last_run = json.loads(Path("artifacts/last_run.json").read_text())
    assert last_run["live_accuracy"] is not None
    assert code in (0, 2)


def test_logreg_model_type(workdir):
    _, data_path = workdir
    code = train.main(["--data", str(data_path), "--model", "logreg", "--min-accuracy", "0.0"])
    assert code == 0
    registry = json.loads(Path("models/registry.json").read_text())
    assert registry["models"][0]["model_type"] == "logreg"


def test_feedback_merged_into_training(workdir, tmp_path):
    from ml.data import init_feedback_db
    import sqlite3

    _, data_path = workdir
    db_path = tmp_path / "feedback.db"
    init_feedback_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO feedback (url, predicted_label, correct_label, model_version) "
        "VALUES (?, ?, ?, ?)",
        ("http://user-flagged-example.com", 1, 0, "1.0"),
    )
    conn.commit()
    conn.close()

    code = train.main([
        "--data", str(data_path),
        "--feedback", str(db_path),
        "--min-accuracy", "0.0",
    ])
    assert code == 0
    last_run = json.loads(Path("artifacts/last_run.json").read_text())
    assert last_run["feedback_rows_merged"] == 1
