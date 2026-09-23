from __future__ import annotations

import logging

from flask import Flask

from app.config import Config
from app.db import init_db
from ml.predict import Predictor, live_model_path


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    init_db(app.config["FEEDBACK_DB_PATH"])

    model_path = app.config["MODEL_PATH"] or live_model_path(app.config["MODEL_REGISTRY_PATH"])
    app.predictor = Predictor(model_path)
    app.logger.setLevel(logging.INFO)
    app.logger.info(
        "Loaded model v%s (%s) from %s", app.predictor.version, app.predictor.model_type, model_path
    )

    from app.routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    return app
