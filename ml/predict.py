"""Load a trained model bundle and score URLs. This is what the Flask app imports."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import joblib

from ml.features import FEATURE_NAMES, explain, features_frame

_URL_RE = re.compile(
    r"^([a-zA-Z][a-zA-Z0-9+.-]*://)?"
    r"([\w.-]+)"
    r"(:\d{1,5})?"
    r"(/[^\s]*)?$"
)


def validate_url(url: str) -> bool:
    """Cheap structural check -- not a network reachability check."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if len(url) < 4 or len(url) > 2048 or " " in url:
        return False
    candidate = url if "://" in url else "http://" + url
    hostname_part = candidate.split("://", 1)[1].split("/", 1)[0]
    hostname_part = hostname_part.split("@")[-1].split(":")[0]
    if not hostname_part or "." not in hostname_part:
        return False
    return bool(_URL_RE.match(url))


class ModelLoadError(RuntimeError):
    pass


class Predictor:
    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise ModelLoadError(f"Model file not found: {model_path}")
        bundle = joblib.load(self.model_path)
        if bundle.get("feature_names") != FEATURE_NAMES:
            raise ModelLoadError(
                "Model was trained with a different feature set than the "
                "current ml.features.FEATURE_NAMES -- retrain from scratch."
            )
        self.model = bundle["model"]
        self.version = bundle["version"]
        self.model_type = bundle.get("model_type", "unknown")
        self.trained_at = bundle.get("trained_at")
        self.accuracy = bundle.get("accuracy")

    def predict(self, url: str) -> dict:
        if not validate_url(url):
            raise ValueError(f"Invalid URL: {url!r}")

        features = features_frame([url])
        label = int(self.model.predict(features)[0])
        proba = self.model.predict_proba(features)[0]
        phishing_index = list(self.model.classes_).index(1)
        phishing_probability = float(proba[phishing_index])

        return {
            "url": url,
            "label": "phishing" if label == 1 else "safe",
            "label_id": label,
            "phishing_probability": phishing_probability,
            "model_version": self.version,
            "reasons": explain(url),
        }


def live_model_path(registry_path: str | Path = "models/registry.json") -> Path:
    """Resolve the currently-promoted model file from the registry."""
    registry_path = Path(registry_path)
    if not registry_path.exists():
        raise ModelLoadError(
            f"No registry at {registry_path} -- run `python -m ml.train` first."
        )
    registry = json.loads(registry_path.read_text())
    live_version = registry.get("live_version")
    if not live_version:
        raise ModelLoadError("Registry has no live_version -- no model has been promoted yet.")
    for entry in registry["models"]:
        if entry["version"] == live_version:
            return Path(entry["path"])
    raise ModelLoadError(f"live_version {live_version!r} not found in registry entries.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: python -m ml.predict <url> [--model-path PATH]", file=sys.stderr)
        return 1

    url = argv[0]
    model_path = None
    if "--model-path" in argv:
        model_path = argv[argv.index("--model-path") + 1]
    else:
        model_path = live_model_path()

    predictor = Predictor(model_path)
    result = predictor.predict(url)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
