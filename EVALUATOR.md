# Showing the evaluator Docker and Jenkins

What to run, what to point at, and what each thing proves. Everything here
has already been run for real on this machine — see `REPORT.md` §8.

Start the stack **10 minutes before** the evaluation:

```bash
./demo-up.sh
```

It starts Docker Desktop, Jenkins and the containers, waits for each to become
healthy, and prints the three URLs. Tear down afterwards with `./demo-down.sh`.

---

## Part A — Docker (experiments 4, 5, 9)

### A1. The containers are really running

```bash
docker compose ps
```

Point at the **`healthy`** status on both containers. Say: health is not
cosmetic — `/health` returns 503 if the model fails to load, so a container
that shipped a broken model would show as unhealthy instead of quietly
serving errors.

### A2. Images are versioned, not just `latest`

```bash
docker images phishguard
```

Each tag is **this code plus that exact model**. Rolling back a bad model is
running an older tag — nothing to rebuild, nothing to un-merge.

### A3. The named volume is what makes the loop work

```bash
docker volume ls | grep feedback
docker compose exec app ls -la /app/data/feedback/
```

This is the point worth making: user corrections live in a **named volume**,
not in the container. Show it concretely —

1. Submit a correction in the app (`http://localhost:5050`).
2. `docker compose restart app`
3. The correction is still in the dashboard.

Without the volume, every deploy would throw away the data the whole
self-improving design depends on. This was a real bug, found by running it:
`REPORT.md` §8, bug 1.

### A4. Security (experiment 8, listed topic 8)

```bash
docker compose exec app whoami          # not root
trivy image --severity HIGH,CRITICAL phishguard:local | tail -20
```

Have the Pillow story ready: the scan found 13 HIGH CVEs in Pillow 10.4.0,
pulled in transitively by Streamlit, all in image codecs the app never
touches. Pinning Pillow to 12.3.0 removed all 13 with no behaviour change.
Finding something real, and fixing it, is the answer — not a clean scan.

---

## Part B — Jenkins (experiments 2, 3, 8, 9)

Open `http://localhost:8080` → the **phishguard** pipeline job.

### B1. Show a completed run first

Open build **#3** → **Pipeline Overview**. Twelve stages green in 2m 26s.
Walk left to right once, naming what each stage protects against. Do not
start a fresh build yet — if it fails you have nothing to show.

### B2. Open the Console Output of two stages

- **Merge feedback + Train** — shows the row counts: dataset rows + feedback
  rows merged, then the accuracy of the candidate.
- **Selenium tests** — shows a real headless Chrome driving the freshly built
  container on a side port, before it is allowed near production.

### B3. The accuracy gate is the centrepiece

Open the build where the gate **rejected** a candidate. Point at:

- the build is **yellow (UNSTABLE)**, not red — rejection is a normal
  outcome, not a crash;
- Build Image, Selenium, Trivy and Deploy were **skipped**;
- the app still reports the previous version afterwards.

Say this explicitly: *the candidate and the live model are scored on the same
held-out split.* Once feedback changes the data, the live model's stored
accuracy was measured on a different split and is no longer comparable. This
is the single design decision most worth defending.

### B4. Now trigger a live run

```bash
git commit --allow-empty -m "Demo: trigger pipeline" && git push
```

Narrate the stages as they go green. If the webhook is not reachable from the
lab network, press **Build Now** and say so — the webhook is configured, the
trigger is the only difference.

### B5. Artifacts

On the build page, open **Archived Artifacts** → `last_run.json`. Every run,
promoted or rejected, is recorded with its metrics, a hash of the training
data, the Git commit and the build number. That is the audit trail: you can
say exactly which model is live and which commit produced it.

---

## If something breaks

| Symptom | Say this, then do this |
|---|---|
| Docker Desktop slow to start | "Cold start." Keep talking through the architecture diagram; `demo-up.sh` is still waiting. |
| A pipeline stage fails live | Open the Console Output and read the error aloud. A pipeline that catches a real failure in the room is a better answer than a staged green run. |
| Webhook does not fire | Press **Build Now**, say the webhook is configured but the lab network blocks the callback. |
| Port 5050 busy | `APP_PORT=5055 ./demo-up.sh` (AirPlay Receiver holds 5000 on macOS). |
| Everything is on fire | Fall back to build #3's recorded run and `REPORT.md` §8. |

**Record a screen capture of one full green run the night before.** If the lab
Wi-Fi or Docker misbehaves you still have evidence, and you will be calmer for
having it.

---

## The three sentences to land

1. The model is retrained from real user corrections, not just once at the start.
2. A new model ships **only** if it beats the live one on the same test split —
   and we can show a build where it did not, and was correctly blocked.
3. Running this for real, rather than only writing it, caught two bugs that
   review did not: the feedback storage mismatch and the gate's environment
   block (`REPORT.md` §8).
