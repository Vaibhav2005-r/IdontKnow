# Live demo script

Shows the whole loop: wrong prediction → user feedback → pipeline run →
gate decision → new version live in the UI. ~5 minutes.

## Setup (before the room fills up)

```bash
source .venv/bin/activate
python -m ml.train --data data/raw/phishing_urls.csv   # get to v1.0 if not already there
PORT=5050 python wsgi.py &                              # or plain 5000 on Windows/Linux
streamlit run dashboard/app.py &
```

Open two browser tabs: the app (`http://localhost:5050`) and the dashboard
(`http://localhost:8501`). Have a terminal visible for the Jenkins/training
step.

## 1. Show the app catches an obvious phish

On the app tab, click the **fake PayPal login** example chip (or paste
`http://paypal-secure-login.tk/verify?id=88231`). Point out:
- the verdict, the probability gauge, the model version badge
- this is a lexical-only model — no network call was made to that URL

## 2. Show it get something wrong, and correct it

Paste a URL the model is likely to misjudge — a legitimate-looking site
with an unusual structure, e.g. a long-path SaaS login URL. If it says
"safe" but you're demonstrating a false negative (or vice versa), narrate
that explicitly, then click **This is wrong**. Point at the confirmation
text: *"logged for the next training run."*

## 3. Prove it landed in the database

```bash
sqlite3 data/feedback/feedback.db "select * from feedback order by id desc limit 3;"
```
Point out `predicted_label` vs `correct_label` on the row you just flagged.

## 4. Run the pipeline

```bash
python -m ml.train --data data/raw/phishing_urls.csv --feedback data/feedback/feedback.db
```
Narrate the JSON output live: `candidate_accuracy` vs `live_accuracy`,
`gate_threshold`, `promoted`. This is exactly what the Jenkinsfile's
"Merge feedback + Train" + "Accuracy gate" stages do — if you have Jenkins
running, trigger the same job here instead (`Build Now` or a `git push`)
and watch the Blue Ocean stage view instead of the raw JSON.

## 5. Show the gate decision either way

- **Promoted**: refresh the dashboard — new row in the registry table, the
  accuracy-over-time chart gets a new green dot, "Live version" ticks up.
  Restart the app (or `docker compose up -d --build` if running
  containerized) and show the version badge in the header changed.
- **Rejected**: exit code `2`, the dashboard's accuracy chart shows a red ✕
  for that run, and the live model — and the badge in the app — are
  unchanged. This is the gate doing its job: a worse model never ships.

## 6. Wrap-up talking points

- Nine lab experiments touched: Git/GitHub (this repo + the GitHub Actions
  sanity CI), Jenkins setup + CI/CD (the `Jenkinsfile`), Docker commands +
  containerized app (`Dockerfile`, `docker-compose.yml`), Selenium setup +
  testing (`tests/ui/`), ML in CI/CD (the Train + gate stages), deployment
  via Jenkins + Docker (the Deploy stage).
- The accuracy gate uses `>=`, not `>` — an equally accurate model trained
  on more feedback still ships, so the system keeps learning even when
  accuracy plateaus.
- Model files never get smarter in place — every promotion is a new
  versioned artifact in `models/registry.json`, so you can always roll back
  by pointing `MODEL_PATH` at an older file.
