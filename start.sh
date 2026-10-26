#!/usr/bin/env bash
# Start PhishGuard: the web app and the monitoring dashboard.
#
#   ./start.sh          app on :5050, dashboard on :8501
#   ./start.sh 5000     app on a port of your choice
#
# Stop both with ./stop.sh (or Ctrl-C in this terminal).

set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-5050}"
DASH_PORT="${DASH_PORT:-8501}"

if [ ! -x .venv/bin/python ]; then
    echo "No virtualenv found. Create it first:"
    echo "    python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt"
    exit 1
fi

# Train a baseline the first time, so a fresh clone starts with a live model.
if [ ! -f models/registry.json ]; then
    echo "No model yet - training a baseline (takes about a minute)..."
    .venv/bin/python -m ml.train --data data/raw/phishing_urls.csv
fi

mkdir -p logs
echo "Starting PhishGuard..."

PORT="$PORT" .venv/bin/python wsgi.py > logs/app.log 2>&1 &
echo $! > logs/app.pid

.venv/bin/streamlit run dashboard/app.py \
    --server.port "$DASH_PORT" --server.headless true > logs/dashboard.log 2>&1 &
echo $! > logs/dashboard.pid

# Wait for the app to answer before declaring success.
for _ in $(seq 1 30); do
    if curl -fsS "http://localhost:$PORT/health" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo
if curl -fsS "http://localhost:$PORT/health" >/dev/null 2>&1; then
    VERSION=$(curl -fsS "http://localhost:$PORT/health" 2>/dev/null)
    echo "  App        http://localhost:$PORT"
    echo "  Dashboard  http://localhost:$DASH_PORT"
    echo "  Health     $VERSION"
    echo
    echo "  Logs       logs/app.log  logs/dashboard.log"
    echo "  Stop       ./stop.sh"
else
    echo "The app did not come up. Last lines of logs/app.log:"
    tail -20 logs/app.log
    exit 1
fi
