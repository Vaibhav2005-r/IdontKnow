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
- the mascot: neutral → scanning (pulsing scan beam) → alarmed (shake, red
  glow, "!" badge) as the verdict comes back — it's not decorative, its
  state is driven directly by the API response
- the **Reasons** list under the gauge (".tk TLD", "no HTTPS", bait words,
  hyphens in the hostname) — a simple rule-based explainer, deliberately
  not SHAP (that's future scope, see REPORT.md)
- this is a lexical-only model — no network call was made to that URL

## 2. Show it get something wrong, and correct it

Paste a URL the model is likely to misjudge — a legitimate-looking site
with an unusual structure, e.g. a long-path SaaS login URL. If it says
"safe" but you're demonstrating a false negative (or vice versa), narrate
that explicitly, then click **No, report it** under "Was this prediction
correct?". Point at the confirmation text: *"logged for the next training
run."* (The mascot turns happy/green for a correct "Safe" call if you click
**Yes** instead — both paths are live, not mocked.)

## 1.5. Walk the pipeline diagram

Scroll to **How PhishGuard Works** and click **Play the walkthrough**. It
animates the exact path a prediction and a correction take through the
system — User → Flask → Feedback DB → (webhook/cron) → Jenkins
(Train→Gate→Test→Scan) → Docker Image → back to the deployed app, and
Jenkins → Dashboard — with each stage's caption explaining what happens
there. Click any box directly to jump to its explanation instead. This is
the fastest way to give the room the whole architecture in 30 seconds
before diving into the live steps below.

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
