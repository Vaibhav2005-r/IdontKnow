"""Runtime configuration, entirely from environment variables with sane defaults.

No secrets live in this repo -- DB paths, model paths, and the Flask secret
key all come from the environment so Jenkins/Docker can override them.
"""
from __future__ import annotations

import os


class Config:
    FEEDBACK_DB_PATH = os.environ.get("FEEDBACK_DB_PATH", "data/feedback/feedback.db")
    MODEL_REGISTRY_PATH = os.environ.get("MODEL_REGISTRY_PATH", "models/registry.json")
    MODEL_PATH = os.environ.get("MODEL_PATH")  # explicit override; else resolved from registry
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    JSON_SORT_KEYS = False
