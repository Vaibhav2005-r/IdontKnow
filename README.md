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

| | macOS | Windows |
|---|---|---|
| Git | `brew install git` (or already present) | [Git for Windows](https://git-scm.com/download/win) — installs Git Bash too |
| Python | 3.12 — `brew install python@3.12` | 3.12 from [python.org](https://www.python.org/downloads/) — **tick "Add python.exe to PATH"** on the first installer screen |
| Docker | [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) | [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) — needs WSL2, see below |
| Chrome | for the Selenium tests | for the Selenium tests |
| Shell | Terminal, zsh/bash (commands below as written) | PowerShell (commands below as written) — Git Bash also works with the macOS-style commands |

The full stack (`docker compose up --build`) has been verified end-to-end on
macOS with Docker Desktop: both containers come up `healthy`, the app and
dashboard correctly share the `feedback_data` named volume (a correction
submitted through the app UI showed up in the dashboard immediately and
survived an `app` container restart), and `trivy image` runs cleanly
against the built image (see `REPORT.md` §8 for the one real finding it
caught and how it was fixed). The Windows steps below use the same
commands the project's own `wsgi.py`/`docker-compose.yml` support — they
follow the same code path as macOS, just via `python.org`'s Python and
PowerShell instead of Homebrew and zsh.

### Docker on Windows — WSL2

Docker Desktop for Windows requires WSL2. If this is a fresh machine:
1. Open PowerShell **as Administrator** and run `wsl --install`, then reboot.
2. Install Docker Desktop, and when it first launches confirm **Settings →
   General → "Use the WSL 2 based engine"** is checked.
3. If Docker Desktop complains about virtualization, enable it in your
   PC's BIOS/UEFI (setting is usually called "Intel VT-x", "AMD-V", or
   "SVM Mode").

Full official walkthrough if you hit issues:
https://docs.docker.com/desktop/setup/install/windows-install/

## Get the code

```bash
git clone https://github.com/Vaibhav2005-r/IdontKnow.git
cd IdontKnow
```
(PowerShell: identical — `git clone ...` then `cd IdontKnow`.)

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
```
Open a **second** terminal tab for the dashboard (keep the app running in the first):
```bash
source .venv/bin/activate
streamlit run dashboard/app.py
# open http://localhost:8501
```
Tests, in either terminal (stop the dev server first, or use a third tab):
```bash
pytest -m "not ui"                                          # unit tests
APP_BASE_URL=http://localhost:5050 pytest tests/ui -m ui     # Selenium, needs the app running
```

## Quickstart — Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```
If that second line fails with *"running scripts is disabled on this
system"*, PowerShell's execution policy is blocking it — this is normal on
a fresh Windows install, not a broken environment. Fix once per machine:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
then re-run `.venv\Scripts\Activate.ps1`. Your prompt should now start with
`(.venv)`. Continue:
```powershell
pip install -r requirements-dev.txt

python -m ml.train --data data/raw/phishing_urls.csv

python wsgi.py
# open http://localhost:5000
```
Open a **second** PowerShell window for the dashboard (re-activate the venv there too):
```powershell
.venv\Scripts\Activate.ps1
streamlit run dashboard/app.py
# open http://localhost:8501
```
Tests, in either window:
```powershell
pytest -m "not ui"
$env:APP_BASE_URL = "http://localhost:5000"
pytest tests/ui -m ui
```
Windows doesn't have macOS's ControlCenter port-5000 conflict, so `PORT=`
usually isn't needed — but if something else on the machine already owns
5000, set it the same way: `$env:PORT = "5050"` before `python wsgi.py`,
and use that port in the URL and in `$env:APP_BASE_URL` above.

## Docker (either OS, once Docker Desktop is running)

```bash
docker compose up --build
# app:       http://localhost:5050   (host port; container listens on 5000)
# dashboard: http://localhost:8501
```
(PowerShell: same command, same URLs — Docker Compose's CLI is identical
on both OSes.)

Host port 5050 is set in `docker-compose.yml` because macOS often has
ControlCenter/AirPlay squatting on 5000 — override with `APP_PORT=5000
docker compose up --build` (macOS/Linux) or `$env:APP_PORT="5000"; docker
compose up --build` (PowerShell) on a machine where 5000 is free.

The image bakes in whatever is in `models/` at build time — train first
(`python -m ml.train ...`, either Quickstart above), then build, so the
container serves the model you just promoted.

`gunicorn` (in requirements.txt) only runs inside the Linux Docker image —
it doesn't work on Windows. Local dev on any OS uses `python wsgi.py`
(Flask's own dev server), as in the Quickstarts above; `pip install` still
succeeds on Windows since gunicorn is just unused there, not broken.

## Troubleshooting

- **Windows: `.venv\Scripts\Activate.ps1` — "running scripts is disabled
  on this system"** → PowerShell's execution policy; see the fix under
  the Windows quickstart above.
- **`Cannot connect to the Docker daemon`** (either OS) → Docker Desktop
  isn't running. Launch it from the Start menu / Applications and wait
  for its whale icon to show "running" before retrying.
- **`docker compose` port already allocated** → something else (or a
  leftover container) already has that port. Free it with `docker compose
  down`, or pick another port (`APP_PORT=...` as above).
- **`python -m ml.train` or the app fails to import scikit-learn/pandas**
  → you're not in the venv, or installed into the wrong Python. Confirm
  the prompt shows `(.venv)`; on Windows confirm `py -3.12 -m venv .venv`
  actually used 3.12 (`py -0` lists installed versions).
- **Selenium tests can't find Chrome/chromedriver** → install Google
  Chrome normally; `webdriver-manager` (already in
  requirements-dev.txt) downloads a matching driver automatically on
  first run — this needs an internet connection the first time.
- **Windows PowerShell — `python` not found** → the installer's "Add
  python.exe to PATH" step was skipped; either re-run the installer and
  tick it, or use `py -3.12` in place of `python` for the venv-creation
  step only (once the venv is active, plain `python` inside it works).

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

This has been run end-to-end against a real local Jenkins (2.568.3): a
Pipeline job pointed at this repo passed all twelve stages, promoted and
deployed v1.0, then correctly rejected a worse candidate (real user
feedback submitted through the live app) and skipped the build/deploy
stages on that run. See `REPORT.md` §8 for the two real bugs that surfaced
along the way and how they were fixed.

Quick local setup, if you want to reproduce this (macOS):
```bash
brew install --cask docker   # if not already installed
brew install jenkins-lts trivy
brew services start jenkins-lts   # http://localhost:8080, follow the setup wizard
```
Then create a Pipeline job → "Pipeline script from SCM" → Git →
`https://github.com/Vaibhav2005-r/IdontKnow.git` (or your own local clone
path), branch `main`, script path `Jenkinsfile`. On Windows, install
Jenkins from the [official installer](https://www.jenkins.io/download/)
or run it as a container instead — the agent still needs Python 3.12,
Docker, Chrome, and Trivy on its `PATH`.

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
