from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request

from app.db import get_feedback_row, insert_prediction, record_correction, stats
from ml.predict import validate_url

bp = Blueprint("routes", __name__)


def _wants_json() -> bool:
    if request.is_json:
        return True
    return request.accept_mimetypes.best == "application/json"


@bp.get("/")
def index():
    predictor = current_app.predictor
    return render_template(
        "index.html",
        model_version=predictor.version,
        model_type=predictor.model_type,
        model_accuracy=predictor.accuracy,
        result=None,
        error=None,
        submitted_url="",
    )


@bp.post("/predict")
def predict():
    predictor = current_app.predictor
    db_path = current_app.config["FEEDBACK_DB_PATH"]

    payload = request.get_json(silent=True) or {}
    url = (payload.get("url") if payload else None) or request.form.get("url", "")
    url = url.strip()

    if not validate_url(url):
        message = "That doesn't look like a valid URL."
        if _wants_json():
            return jsonify({"error": message}), 400
        return render_template(
            "index.html",
            model_version=predictor.version,
            model_type=predictor.model_type,
            model_accuracy=predictor.accuracy,
            result=None,
            error=message,
            submitted_url=url,
        ), 400

    result = predictor.predict(url)
    feedback_id = insert_prediction(db_path, url, result["label_id"], result["model_version"])
    result["feedback_id"] = feedback_id

    if _wants_json():
        return jsonify(result)

    return render_template(
        "index.html",
        model_version=predictor.version,
        model_type=predictor.model_type,
        model_accuracy=predictor.accuracy,
        result=result,
        error=None,
        submitted_url=url,
    )


@bp.post("/feedback")
def feedback():
    db_path = current_app.config["FEEDBACK_DB_PATH"]
    payload = request.get_json(silent=True) or request.form

    try:
        feedback_id = int(payload.get("feedback_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "feedback_id is required"}), 400

    row = get_feedback_row(db_path, feedback_id)
    if row is None:
        return jsonify({"error": f"No prediction with id {feedback_id}"}), 404

    corrected_label = 1 - row["predicted_label"]
    ok = record_correction(db_path, feedback_id, corrected_label)
    if not ok:
        return jsonify({"error": "Could not record correction"}), 500

    return jsonify({
        "status": "recorded",
        "feedback_id": feedback_id,
        "url": row["url"],
        "predicted_label": row["predicted_label"],
        "correct_label": corrected_label,
    })


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "model_loaded": hasattr(current_app, "predictor")})


@bp.get("/version")
def version():
    predictor = current_app.predictor
    return jsonify({
        "model_version": predictor.version,
        "model_type": predictor.model_type,
        "trained_at": predictor.trained_at,
        "accuracy": predictor.accuracy,
        "feedback_stats": stats(current_app.config["FEEDBACK_DB_PATH"]),
    })
