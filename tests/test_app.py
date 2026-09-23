import json

import pytest

from app import create_app
from app.config import Config
from ml import train as ml_train
from ml.sample_data import generate_sample_dataset


class TestConfig(Config):
    pass


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_path = tmp_path / "data.csv"
    generate_sample_dataset(n=200, seed=7).to_csv(data_path, index=False)
    code = ml_train.main(["--data", str(data_path), "--min-accuracy", "0.0"])
    assert code == 0

    TestConfig.FEEDBACK_DB_PATH = str(tmp_path / "feedback.db")
    TestConfig.MODEL_REGISTRY_PATH = "models/registry.json"
    TestConfig.MODEL_PATH = None

    flask_app = create_app(TestConfig)
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_index_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"url-input" in resp.data
    assert b"check-btn" in resp.data


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_version(client):
    resp = client.get("/version")
    body = resp.get_json()
    assert body["model_version"] == "1.0"
    assert "feedback_stats" in body


def test_predict_json_safe_url(client):
    resp = client.post(
        "/predict",
        data=json.dumps({"url": "https://example.com"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["label"] in ("safe", "phishing")
    assert "feedback_id" in body
    assert "phishing_probability" in body


def test_predict_invalid_url_returns_400(client):
    resp = client.post(
        "/predict",
        data=json.dumps({"url": ""}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_predict_html_form_renders_result(client):
    resp = client.post("/predict", data={"url": "https://example.com"})
    assert resp.status_code == 200
    assert b"result--visible" in resp.data or b"result--safe" in resp.data or b"result--phishing" in resp.data


def test_feedback_flips_label(client):
    predict_resp = client.post(
        "/predict",
        data=json.dumps({"url": "http://192.168.1.1/login.php"}),
        content_type="application/json",
    )
    predicted = predict_resp.get_json()

    fb_resp = client.post(
        "/feedback",
        data=json.dumps({"feedback_id": predicted["feedback_id"]}),
        content_type="application/json",
    )
    assert fb_resp.status_code == 200
    body = fb_resp.get_json()
    assert body["correct_label"] == 1 - predicted["label_id"]


def test_feedback_unknown_id_404(client):
    resp = client.post(
        "/feedback",
        data=json.dumps({"feedback_id": 999999}),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_feedback_written_reaches_load_feedback(client, tmp_path):
    from ml.data import load_feedback

    predict_resp = client.post(
        "/predict",
        data=json.dumps({"url": "https://example.org"}),
        content_type="application/json",
    )
    predicted = predict_resp.get_json()
    client.post(
        "/feedback",
        data=json.dumps({"feedback_id": predicted["feedback_id"]}),
        content_type="application/json",
    )

    df = load_feedback(tmp_path / "feedback.db")
    assert "https://example.org" in df["url"].values
