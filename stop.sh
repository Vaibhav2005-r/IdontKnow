#!/usr/bin/env bash
# Stop whatever start.sh started.
cd "$(dirname "$0")"
for name in app dashboard; do
    if [ -f "logs/$name.pid" ]; then
        kill "$(cat logs/$name.pid)" 2>/dev/null && echo "stopped $name"
        rm -f "logs/$name.pid"
    fi
done
# Catch strays from an earlier run started by hand.
pkill -f "streamlit run dashboard/app.py" 2>/dev/null || true
pkill -f "python wsgi.py" 2>/dev/null || true
echo "done"
