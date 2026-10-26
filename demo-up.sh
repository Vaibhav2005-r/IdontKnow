#!/usr/bin/env bash
# Bring up everything an evaluator needs to see, in order:
#   Docker Desktop -> Jenkins -> the containerised app + dashboard
#
#   ./demo-up.sh
#
# Run this ~10 minutes before the demo: Docker Desktop and Jenkins both take
# a while to become ready, and you do not want to be waiting on them in front
# of the examiner. Tear it down afterwards with ./demo-down.sh

set -uo pipefail
cd "$(dirname "$0")"

APP_PORT="${APP_PORT:-5050}"
step() { printf '\n[%s] %s\n' "$1" "$2"; }
ok()   { printf '   ok  %s\n' "$1"; }
bad()  { printf '   !!  %s\n' "$1"; }

# ---------------------------------------------------------------- 1. Docker
step 1/4 "Docker Desktop"
if ! command -v docker >/dev/null 2>&1; then
    bad "docker not on PATH. Install Docker Desktop, then re-run."
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "   starting Docker Desktop (this takes 30-60s on a cold boot)..."
    open -a Docker 2>/dev/null || true
    for _ in $(seq 1 90); do
        docker info >/dev/null 2>&1 && break
        sleep 2
    done
fi
if docker info >/dev/null 2>&1; then
    ok "docker daemon is up ($(docker --version | cut -d, -f1))"
else
    bad "Docker Desktop did not become ready. Open it by hand and re-run."
    exit 1
fi

# --------------------------------------------------------------- 2. Jenkins
step 2/4 "Jenkins"
if command -v brew >/dev/null 2>&1 && brew services list 2>/dev/null | grep -q jenkins-lts; then
    brew services start jenkins-lts >/dev/null 2>&1 || true
else
    bad "jenkins-lts not installed via brew; start your Jenkins by hand."
fi
for _ in $(seq 1 45); do
    curl -fsS -o /dev/null http://localhost:8080/login 2>/dev/null && break
    sleep 2
done
if curl -fsS -o /dev/null http://localhost:8080/login 2>/dev/null; then
    ok "Jenkins answering on http://localhost:8080"
else
    bad "Jenkins is not answering on :8080 yet - give it another minute."
fi

# ------------------------------------------------------- 3. the application
step 3/4 "Containerised app + dashboard"
echo "   building and starting (first build takes a few minutes)..."
if APP_PORT="$APP_PORT" docker compose up --build -d; then
    ok "compose finished"
else
    bad "docker compose failed - see the output above"
    exit 1
fi

echo "   waiting for health checks..."
for _ in $(seq 1 60); do
    curl -fsS -o /dev/null "http://localhost:$APP_PORT/health" 2>/dev/null && break
    sleep 2
done

# ------------------------------------------------------------- 4. the recap
step 4/4 "Status"
docker compose ps
echo
if curl -fsS -o /dev/null "http://localhost:$APP_PORT/health" 2>/dev/null; then
    ok "app     http://localhost:$APP_PORT"
    echo "       $(curl -fsS "http://localhost:$APP_PORT/health" 2>/dev/null)"
else
    bad "app is not answering on :$APP_PORT - docker compose logs app"
fi
curl -fsS -o /dev/null http://localhost:8501 2>/dev/null \
    && ok "dash    http://localhost:8501" \
    || bad "dashboard not answering on :8501 yet (Streamlit is slow to boot)"
curl -fsS -o /dev/null http://localhost:8080/login 2>/dev/null \
    && ok "jenkins http://localhost:8080"

cat <<'TIP'

   Open these three tabs before the evaluator arrives:
     http://localhost:5050    the app
     http://localhost:8501    the dashboard
     http://localhost:8080    Jenkins (the phishguard pipeline job)

   Useful during the demo:
     docker compose ps                 containers + health
     docker images phishguard          the tagged image versions
     docker compose logs -f app        live request log
     ./demo-down.sh                    stop everything afterwards
TIP
