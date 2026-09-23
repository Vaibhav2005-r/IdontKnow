# PhishGuard — Project Report

**T.E. Semester V, PS-4 / DevOps-MLOps Laboratory**
**Department of Artificial Intelligence & Data Science, TCET**

Team: Aayush Thakkar (25) · Manasvi Dholariya (26) · Vaibhav Dohare (27)
Guide: Mr. Aditya Yadav

> This is a working draft covering the technical content the report needs.
> Reformat into the department's official template (cover page, certificate,
> declaration, index) before submission.

## 1. Abstract

Phishing URLs are typically detected either by blocklists (reactive, always
a step behind new domains) or by models that need to fetch the destination
page (slow, and requires visiting a potentially malicious site before
judging it). PhishGuard classifies a URL from its string alone — no DNS,
WHOIS, or HTTP request — so a verdict is instant and safe to compute even
for a URL that turns out to be actively malicious. On top of the classifier,
PhishGuard implements a full MLOps loop: user corrections are captured as
feedback, a Jenkins pipeline retrains on that feedback, an accuracy gate
compares the candidate against the currently deployed model on an identical
held-out split, and only a model that is at least as accurate is promoted
and deployed.

## 2. Problem statement

Build a phishing URL detector that (a) classifies in real time without
contacting the target URL, (b) improves from user-reported mistakes rather
than staying frozen at its training-time accuracy, and (c) demonstrates a
complete CI/CD pipeline for a machine learning system — not just for
application code — including an automated go/no-go gate before any new
model reaches users.

## 3. System architecture

```
 user ──▶ Flask app (app/) ──▶ SQLite feedback.db
              │  loads model            ▲
              ▼  via registry.json      │ read on retrain
         models/*.joblib ◀── ml/train.py (gated) ◀── data/raw + feedback.db
              │
              ▼
      Streamlit dashboard (dashboard/)
```

- **`ml/`** — framework-free Python: feature extraction, dataset loading,
  training + gate, and prediction. Testable and runnable identically from a
  shell, the Flask app, or a Jenkins agent.
- **`app/`** — Flask. Loads one `Predictor` at process start, serves
  `GET /`, `POST /predict` (JSON or HTML), `POST /feedback`, `GET /health`,
  `GET /version`.
- **`dashboard/`** — Streamlit, read-only against the model registry, the
  run history, and the feedback DB.
- **Jenkins** — orchestrates retraining, gating, testing, and deployment.
- **Docker** — the deployable unit; one image tag = one model version.

### Frontend

The UI ([app/templates/index.html](../app/templates/index.html),
[app/static/](../app/static/)) is hand-built HTML/CSS/vanilla JS — no
framework, no build step, no CDN dependency, so it works offline and stays
simple enough for a viva walkthrough of the source. Two things beyond a
plain form-and-result page:

- **A live mascot.** An inline SVG shield character whose face, eyebrows,
  and a badge icon are driven directly by application state — idle while
  waiting, a pulsing scan animation while `POST /predict` is in flight,
  then a happy green bounce or an alarmed red shake once the verdict comes
  back. It's wired to the same fetch response the result card renders, not
  a separate mock.
- **An interactive pipeline diagram** ("How PhishGuard Works" section): an
  SVG rendering of the architecture above plus the Jenkins stage sequence,
  with every node clickable (shows a plain-English caption of what that
  component does) and a "Play the walkthrough" button that animates the
  actual path a prediction and a correction take through the system, end
  to end, stage by stage.
- **Reasons.** Each verdict includes a short list of human-readable reasons
  (`ml.features.explain()`) — e.g. *"uses the .tk TLD"*, *"no HTTPS"*, *"3
  bait words in the URL"*. This is deliberately simple, rule-based logic
  over the same signals the model trains on, not SHAP — full feature
  attribution is listed under Future Scope (§10) rather than implemented
  here, since a rule-based explanation is enough to make a verdict legible
  without adding a second, harder-to-verify explanation model.

## 4. Dataset

**Web Page Phishing Detection** (Hannousse & Yahiouche, 2021; also
distributed via Kaggle and Mendeley Data). 11,430 URLs, balanced (5,715
phishing / 5,715 legitimate). We keep only the `url` and `status` columns —
the source dataset's other 87 columns require live page content or
WHOIS/DNS lookups, which are unavailable (and undesirable — see §2) at
prediction time.

**Sanity check performed before training:** both classes use the same URL
formatting (scheme present on 100% of both classes; both classes mix
`http://` and `https://`), so the model cannot shortcut on a formatting
artifact instead of learning real signal.

## 5. Feature engineering

32 lexical features computed from the URL string alone (`ml/features.py`),
including: URL/hostname/path/query length, punctuation and special-character
counts, digit ratio, subdomain count, TLD length, IP-literal hostname
detection, HTTPS flag, port presence, known URL-shortener detection,
redirect-marker count (`//`), Shannon entropy of the full URL, a
suspicious-keyword count (`login`, `verify`, `secure`, `account`, …), and
path-segment statistics. Full list and rationale in `ml/features.py`.

## 6. Model and results

Random Forest (200 trees), trained on an 80/20 stratified split of the
11,429 deduplicated URLs.

| Model | Accuracy (held-out) |
|---|---|
| Random Forest, 200 trees (URL-only features) | **89.0%** |
| Logistic Regression (URL-only features), for comparison | see `python -m ml.train --model logreg` |
| Sahingoz et al. (2019), literature best, URL + page + third-party features | 97.98% |

89% from URL-only lexical features is consistent with the literature: models
that also see page content or query external services (WHOIS, DNS,
reputation APIs) score higher, at the cost of speed and of needing to
contact the target. We treat ≥95% as unrealistic for a URL-only model and
a sign of a bug (e.g. leaking a formatting artifact) rather than a result
to celebrate. `ml/sample_data.py`'s synthetic data is intentionally
excluded from this table — it scores near-100% by construction, since it's
generated from the same rules the features look for, and exists only so
tests and CI can run offline.

## 7. The feedback loop and accuracy gate

Every prediction is written to `feedback(id, url, predicted_label,
correct_label, model_version, created_at)` with `correct_label` initially
equal to `predicted_label` (assumed correct). A **This is wrong** click
flips `correct_label` on that row. On retrain, `ml.data.merge_feedback`
overlays the base dataset with feedback by URL — the user's label always
wins on a duplicate URL — before the same train/gate/version flow runs.

The gate (`ml/train.py`) evaluates the candidate and the currently-live
model on the *same* held-out split (not a stored accuracy number, since
data changes between runs) and promotes with `>=`, not `>`: an equally
accurate model trained on more feedback still ships, so the system keeps
absorbing corrections even once accuracy plateaus. A rejected candidate
exits with status code `2`; the Jenkinsfile marks that build UNSTABLE and
skips the build/deploy stages, leaving the live model untouched.

## 8. CI/CD pipeline (Jenkins)

Stages: **Checkout → Setup Python env → Merge feedback + Train → Accuracy
gate → Unit tests → Build image → Selenium tests against the built
container → Trivy scan → Deploy → Archive artifacts.** Triggered by a
GitHub webhook push and a nightly cron. See `Jenkinsfile` and
`DEMO.md` §4–5 for a walkthrough of a real run.

The full stack was built and run end-to-end with Docker Desktop: both
containers report `healthy`, the app and dashboard containers correctly
share the named `feedback_data` volume (a correction submitted through the
app was immediately visible in the dashboard's "User corrections" metric
and survived an app container restart), and a real `trivy image` scan of
the built image found 13 HIGH-severity CVEs in a transitive dependency
(Pillow 10.4.0, pulled in by Streamlit, all image-parsing vulnerabilities
in codecs — PSD/FITS/PCF/BDF/GD/JPEG2000 — the app never decodes). Pinning
Pillow to 12.3.0 (requires Streamlit ≥1.55, which still allows Pillow <13)
in `requirements.txt` removed all 13 without any test or behavior change;
the remaining 44 HIGH findings are in the `python:3.12-slim` base image's
Debian packages and are addressed by the normal practice of rebuilding
against a fresh base image tag periodically, which this pipeline already
does on every run since the base image isn't pinned to a digest.

**The `Jenkinsfile` was also run against a real, locally installed Jenkins
2.568.3** (not just reviewed) — a Pipeline job pointed at this repo's
`main` branch. Build #3 passed all twelve stages
(Checkout → Setup Python env → Merge feedback + Train → Accuracy gate →
Unit tests → Build image → Selenium tests against the built container →
Trivy scan → Deploy → Archive artifacts) in 2m 26s, promoted v1.0, and
deployed it — `docker ps` afterward showed the exact same `phishguard-app`
/ `phishguard-dashboard` containers, now built and started by Jenkins
rather than by hand.

Running it for real, rather than only reading the file, surfaced two
genuine bugs no amount of review caught:

1. **The feedback loop had a storage mismatch.** The live app's
   `feedback.db` lives inside a Docker named volume; the "Merge feedback +
   Train" stage was reading a plain workspace-relative path. Every retrain
   — scheduled or webhook-triggered — would have silently trained on the
   committed dataset only, never on what users actually corrected,
   defeating the project's central premise. Fixed by having that stage
   `docker cp` the live container's `feedback.db` into the workspace
   before training.
2. **A Declarative Pipeline caveat swallowed the gate's own decision.**
   `GATE_REJECTED` was declared in the top-level `environment {}` block
   and then mutated with `env.GATE_REJECTED = 'true'` inside the Train
   stage on rejection. Declarative Pipeline re-injects that block's
   values at stage boundaries, so the very next stage saw it reset to
   `'false'` — one echo line said "gate rejected," the next said "Gate:
   PROMOTED," and the `when { expression { env.GATE_REJECTED != 'true' } }`
   guards on Build/Selenium/Trivy/Deploy let a rejected candidate through
   anyway. Confirmed with a real submitted correction that made the
   candidate score 88.98% against a live 90.11% (correctly rejected by
   `ml.train`'s own gate); caught the pipeline shipping it anyway. Fixed
   by not declaring that variable in `environment {}` at all, and setting
   it explicitly on every path inside the Train stage's own script block,
   where the mutation survives. Re-run confirmed: both echoes now agree,
   and Build/Selenium/Trivy/Deploy show `NOT_EXECUTED`. Because
   `ml.train` itself never writes `registry.json` unless a candidate is
   promoted, the earlier (buggy) run never actually shipped a worse
   *model* — it only wasted a rebuild/redeploy cycle on the unchanged
   live one, which is why this was safe to discover this way rather than
   in front of an audience.

## 9. Lab experiments demonstrated

| # | Experiment | Where |
|---|---|---|
| 1 | Git / GitHub | This repository's history; `.github/workflows/tests.yml` |
| 2 | Jenkins setup | `Jenkinsfile` `agent`/`triggers`/`options` blocks |
| 3 | Jenkins CI/CD | Full `Jenkinsfile` pipeline, §8 above |
| 4 | Docker commands | `Dockerfile`, image build/run in the Jenkinsfile's Build/Selenium/Deploy stages |
| 5 | Containerized app | `docker-compose.yml` running the Flask app + dashboard from one image |
| 6 | Selenium setup | `tests/ui/conftest.py` (webdriver-manager, headless Chrome) |
| 7 | Selenium testing | `tests/ui/test_ui_flow.py` — verdict rendering, feedback submission, error handling |
| 8 | ML in CI/CD | `ml/train.py`'s gate, invoked from the Jenkinsfile's Train + Accuracy gate stages |
| 9 | Deployment via Jenkins + Docker | Jenkinsfile's Deploy stage (`docker compose up -d --build`) |

## 10. Limitations and future work

- URL-only features cannot catch a phish that uses an otherwise-legitimate
  short URL (e.g. a compromised subdomain) — content- or reputation-based
  signals would help but reintroduce the network-call problem this design
  avoids.
- The feedback loop trusts every user equally; a production system would
  weight or rate-limit feedback per source.
- SQLite is adequate for this lab's scale; a multi-instance deployment
  would need a shared database.

## 11. Conclusion

PhishGuard demonstrates that a URL-only lexical classifier reaches a
realistic, literature-consistent accuracy without ever contacting a
potentially malicious destination, and that the harder engineering problem
— safely and automatically improving a deployed model from live user
feedback — can be solved with a small, explainable set of tools: a fixed
feedback schema, a same-split accuracy gate, and a CI/CD pipeline that
treats "reject the candidate" as a normal, successful outcome rather than a
failure.
