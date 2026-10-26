#!/usr/bin/env bash
# Stop the demo stack. The feedback volume is kept on purpose: it holds the
# corrections that drive retraining. Add --wipe only if you want a clean slate.
cd "$(dirname "$0")"
docker compose down
if [ "${1:-}" = "--wipe" ]; then
    docker volume rm phishguard_feedback_data 2>/dev/null \
        && echo "feedback volume removed"
fi
command -v brew >/dev/null 2>&1 && brew services stop jenkins-lts >/dev/null 2>&1 \
    && echo "jenkins stopped"
echo "done (Docker Desktop left running)"
