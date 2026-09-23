# PhishGuard

A self-improving phishing URL detector with a full MLOps pipeline. Paste a
URL, get **Phishing** or **Safe**. Flag a wrong call and the correction is
stored; Jenkins retrains on a push or nightly, gates the new model on
accuracy against the live one, and only promotes it if it's at least as
good. A Streamlit dashboard shows version history and accuracy over time.

Built for **T.E. Sem V, PS-4 / DevOps-MLOps lab, Dept. of AI & DS, TCET**.
Members: Aayush Thakkar (25), Manasvi Dholariya (26), Vaibhav Dohare (27).
Guide: Mr. Aditya Yadav.

See [DEMO.md](DEMO.md) for the live-demo script and [REPORT.md](REPORT.md)
for the write-up mapping this repo to each of the nine lab experiments.

## Architecture

```
                     ┌──────────────┐
   user's browser ──▶│  Flask app   │──▶ SQLite (feedback.db)
                     │  (app/)      │        ▲
                     └──────┬───────┘        │ reads on retrain
                            │ loads           │
                            ▼                 │
                     ┌──────────────┐         │
                     │ models/      │◀────────┘
                     │ registry.json│    ml/train.py
                     │ *.joblib     │◀── (accuracy-gated)
                     └──────┬───────┘
                            │ read by
                            ▼
                     ┌──────────────┐
                     │  Streamlit   │
                     │  dashboard   │
                     └──────────────┘

  Jenkins: Checkout → Train (+feedback) → gate → unit tests → build image
           → Selenium vs. built container → Trivy scan → deploy → archive
```

`ml/` is pure Python with no Flask/Docker dependency, so it trains and
predicts identically whether it's invoked from your shell, the Flask app,
or a Jenkins agent.

## Repo layout

```
ml/          features, data loading, train + accuracy gate, predict
app/         Flask app: prediction API, feedback DB, frontend
dashboard/   Streamlit monitoring dashboard
tests/       pytest unit tests; tests/ui/ = Selenium (needs Chrome)
data/raw/    real dataset (committed)      data/sample/  synthetic (committed)
data/feedback/  feedback.db at runtime (gitignored)
models/      registry.json + phishguard_vX.Y.joblib (gitignored, runtime)
artifacts/   last_run.json + run_history.jsonl for Jenkins/dashboard (gitignored)
Jenkinsfile, Dockerfile, docker-compose.yml
```

## Prerequisites

| | macOS (primary) | Windows |
|---|---|---|
| Python | 3.12 (`brew install python@3.12`) | 3.12 from [python.org](https://www.python.org/downloads/) — check "Add to PATH" |
| Docker | [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) | [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) (needs WSL2) |
| Chrome | for Selenium tests | for Selenium tests |
| Shell commands below | zsh/bash (as written) | use PowerShell equivalents noted inline |

This machine did not have Docker Desktop installed while building the
project, so the `ml/`, Flask, and dashboard pieces were run and verified
directly; the Docker/Compose/Jenkins pieces are written and reviewed but
need Docker Desktop installed before you can `docker build`/`docker compose up`
locally. Install it, then everything below works as written.

## Quickstart — macOS

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# train the first model (promotes v1.0 on ~89% accuracy — realistic for
# URL-only lexical features; see REPORT.md for why)
python -m ml.train --data data/raw/phishing_urls.csv

# run the app (macOS: port 5000 is often taken by ControlCenter/AirPlay —
# use PORT=5050 if `flask run`/wsgi.py fails to bind)
PORT=5050 python wsgi.py
# open http://localhost:5050

# in another terminal: the dashboard
streamlit run dashboard/app.py
# open http://localhost:8501

# unit tests
pytest -m "not ui"

# UI tests (needs the app running + Chrome installed)
APP_BASE_URL=http://localhost:5050 pytest tests/ui -m ui
```

## Quickstart — Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

python -m ml.train --data data/raw/phishing_urls.csv

python wsgi.py
# open http://localhost:5000

# in another terminal
streamlit run dashboard/app.py

pytest -m "not ui"
$env:APP_BASE_URL = "http://localhost:5000"
pytest tests/ui -m ui
```

## Docker (either OS, once Docker Desktop is running)

```bash
docker compose up --build
# app:       http://localhost:5000
# dashboard: http://localhost:8501
```

The image bakes in whatever is in `models/` at build time — train first,
then build, so the container serves the model you just promoted.

`gunicorn` (in requirements.txt) only runs inside the Linux Docker image —
it doesn't work on Windows. Local dev on any OS uses `python wsgi.py`
(Flask's own dev server), as in the Quickstarts above; `pip install` still
succeeds on Windows since gunicorn is just unused there, not broken.

## Everyday commands

```bash
python -m ml.sample_data                                  # offline synthetic data
python -m ml.train --data data/raw/phishing_urls.csv      # train + gate + version
python -m ml.train --data data/raw/phishing_urls.csv --feedback data/feedback/feedback.db
python -m ml.predict "http://192.168.4.20/sbi/kyc/update.php"
pytest -m "not ui"                                         # unit tests
docker compose up --build                                  # full stack
```

## Jenkins

Point a Jenkins Pipeline job at this repo's `Jenkinsfile`. It needs on the
agent: Python 3.12, Docker, Chrome (for the Selenium stage), and the
[Trivy](https://github.com/aquasecurity/trivy) CLI. Wire up a GitHub webhook
(`githubPush()` trigger) for push-triggered runs; it also runs nightly via
cron. No Jenkins credentials are required for the default pipeline — it
builds and deploys locally on the agent via `docker compose`.

## Hard contracts (do not change casually)

- Label convention: `1 = phishing, 0 = safe`, everywhere — dataset, DB, model, API.
- The feedback table schema is owned by `ml.data.FEEDBACK_SCHEMA`; the Flask
  app and `ml.train` must both agree on it.
- `ml.features.FEATURE_NAMES` order is baked into every model file — models
  refuse to load if it differs. Adding a feature means retraining from scratch.
- `ml/train.py` exit codes (`0` promoted, `2` rejected, `1` error) are read
  by the Jenkinsfile — never swallow them.
- The gate compares the candidate and the live model on the *same* held-out
  split, not against a stored accuracy number.
