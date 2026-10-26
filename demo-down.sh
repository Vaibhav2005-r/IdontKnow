#!/usr/bin/env bash
# Stop the demo stack. The feedback volume is kept on purpose: it holds the
# corrections that drive retraining. Add --wipe only if you want a clean slate.
cd "$(dirname "$0")"
docker compose down
if [ "${1:-}" = "--wipe" ]; then
    docker volume rm phishguard_feedback_data 2>/dev/null \
        && echo "feedback volume removed"
fi
# Stop whichever Jenkins we started: brew service, container, or .war.
if [ -f logs/jenkins.pid ]; then
    kill "$(cat logs/jenkins.pid)" 2>/dev/null && echo "jenkins (war) stopped"
    rm -f logs/jenkins.pid
elif command -v brew >/dev/null 2>&1; then
    JF="$(brew services list 2>/dev/null | awk '/^jenkins.*started/ {print $1; exit}')"
    [ -n "$JF" ] && brew services stop "$JF" >/dev/null 2>&1 \
        && echo "jenkins ($JF) stopped"
fi
echo "done (Docker Desktop left running)"
