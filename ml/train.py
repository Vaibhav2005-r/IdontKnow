"""Train a candidate model, gate it against the live model, and version it.

Exit codes (the Jenkinsfile branches on these -- never swallow them):
  0 = candidate promoted to live
  2 = candidate rejected by the accuracy gate
  1 = error (bad data, bad args, crash)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from ml.data import fingerprint, load_dataset, load_feedback, merge_feedback
from ml.features import FEATURE_NAMES, features_frame

MODELS_DIR = Path("models")
ARTIFACTS_DIR = Path("artifacts")
REGISTRY_PATH = MODELS_DIR / "registry.json"
LAST_RUN_PATH = ARTIFACTS_DIR / "last_run.json"
RUN_HISTORY_PATH = ARTIFACTS_DIR / "run_history.jsonl"

_BUILDERS = {
    "rf": lambda: RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1),
    "logreg": lambda: LogisticRegression(max_iter=1000, random_state=42),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {"live_version": None, "models": []}


def _save_registry(registry: dict) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


def _next_version(registry: dict) -> str:
    if not registry["models"]:
        return "1.0"
    latest = max(registry["models"], key=lambda m: tuple(map(int, m["version"].split("."))))
    major, minor = map(int, latest["version"].split("."))
    return f"{major}.{minor + 1}"


def _load_live_model(registry: dict):
    live_version = registry.get("live_version")
    if not live_version:
        return None
    for entry in registry["models"]:
        if entry["version"] == live_version:
            path = Path(entry["path"])
            if path.exists():
                return joblib.load(path)
    return None


def _write_last_run(payload: dict) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN_PATH.write_text(json.dumps(payload, indent=2))
    with RUN_HISTORY_PATH.open("a") as f:
        f.write(json.dumps(payload) + "\n")


def run(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.data)
    if args.feedback:
        feedback = load_feedback(args.feedback)
        dataset = merge_feedback(dataset, feedback)
        feedback_count = len(feedback)
    else:
        feedback_count = 0

    if len(dataset) < 20:
        raise ValueError(f"Not enough training data: {len(dataset)} rows")

    fp = fingerprint(dataset)
    X = features_frame(dataset["url"].tolist())
    y = dataset["label"].to_numpy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    builder = _BUILDERS[args.model]
    candidate = builder()
    candidate.fit(X_train, y_train)
    candidate_accuracy = accuracy_score(y_test, candidate.predict(X_test))

    registry = _load_registry()
    live_bundle = _load_live_model(registry)
    live_accuracy = None
    if live_bundle is not None and live_bundle["feature_names"] == FEATURE_NAMES:
        live_accuracy = accuracy_score(y_test, live_bundle["model"].predict(X_test))

    if args.min_accuracy is not None:
        threshold = args.min_accuracy
    elif live_accuracy is not None:
        threshold = live_accuracy
    else:
        threshold = 0.0

    promoted = candidate_accuracy >= threshold
    version = _next_version(registry) if promoted else None

    result = {
        "timestamp": _now(),
        "model_type": args.model,
        "n_samples": len(dataset),
        "feedback_rows_merged": feedback_count,
        "data_fingerprint": fp,
        "candidate_accuracy": candidate_accuracy,
        "live_accuracy": live_accuracy,
        "gate_threshold": threshold,
        "promoted": promoted,
        "version": version,
        "status": "promoted" if promoted else "rejected",
    }

    if promoted:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        model_path = MODELS_DIR / f"phishguard_v{version}.joblib"
        bundle = {
            "model": candidate,
            "feature_names": FEATURE_NAMES,
            "version": version,
            "model_type": args.model,
            "trained_at": result["timestamp"],
            "accuracy": candidate_accuracy,
            "data_fingerprint": fp,
        }
        joblib.dump(bundle, model_path)

        registry["models"].append({
            "version": version,
            "path": str(model_path),
            "model_type": args.model,
            "accuracy": candidate_accuracy,
            "trained_at": result["timestamp"],
            "data_fingerprint": fp,
            "n_samples": len(dataset),
            "promoted": True,
        })
        registry["live_version"] = version
        _save_registry(registry)
        result["model_path"] = str(model_path)

    _write_last_run(result)

    print(json.dumps(result, indent=2))
    return 0 if promoted else 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and gate a PhishGuard model")
    parser.add_argument("--data", required=True, help="Path to training CSV")
    parser.add_argument("--feedback", default=None, help="Path to feedback SQLite DB or CSV")
    parser.add_argument("--model", choices=list(_BUILDERS), default="rf")
    parser.add_argument("--min-accuracy", type=float, default=None, dest="min_accuracy")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except Exception as exc:  # noqa: BLE001 -- CLI boundary, must report and exit 1
        _write_last_run({
            "timestamp": _now(),
            "status": "error",
            "error": str(exc),
        })
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
