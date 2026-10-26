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

# Docker Desktop installs its CLI in one of several places and only adds it to
# PATH for *new* login shells, so a shell opened before (or during) the install
# will not see it. Look in the known locations before concluding it is missing.
if ! command -v docker >/dev/null 2>&1; then
    for candidate in \
        /usr/local/bin/docker \
        "$HOME/.docker/bin/docker" \
        /opt/homebrew/bin/docker \
        /Applications/Docker.app/Contents/Resources/bin/docker
    do
        if [ -x "$candidate" ]; then
            PATH="$(dirname "$candidate"):$PATH"
            export PATH
            ok "found docker at $candidate (not on your PATH - see note at the end)"
            DOCKER_PATH_FIXUP="$(dirname "$candidate")"
            break
        fi
    done
fi

if ! command -v docker >/dev/null 2>&1; then
    bad "No docker CLI found."
    if [ -d /Applications/Docker.app ]; then
        echo "   Docker Desktop IS installed (/Applications/Docker.app) but its"
        echo "   command-line tool is missing. Open Docker Desktop once and let it"
        echo "   finish setting up, then re-run this script."
    else
        echo "   Docker Desktop does not appear to be installed. Install it with:"
        echo "       brew install --cask docker"
        echo "   then open it once (it asks for a password on first run) and re-run."
    fi
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

# Jenkins gets installed several ways (brew jenkins-lts, brew jenkins, a .war,
# or a container), so detect what is actually here rather than assuming one.
if curl -fsS -o /dev/null http://localhost:8080/login 2>/dev/null; then
    ok "Jenkins is already running on http://localhost:8080"
else
    JENKINS_STARTED=""

    # 1. Homebrew service, under either formula name.
    if command -v brew >/dev/null 2>&1; then
        JENKINS_FORMULA="$(brew services list 2>/dev/null \
            | awk '/^jenkins/ {print $1; exit}')"
        if [ -n "$JENKINS_FORMULA" ]; then
            echo "   starting $JENKINS_FORMULA via brew services..."
            brew services start "$JENKINS_FORMULA" >/dev/null 2>&1 || true
            JENKINS_STARTED="brew:$JENKINS_FORMULA"
        fi
    fi

    # 2. A Jenkins container (named jenkins*, running or stopped).
    if [ -z "$JENKINS_STARTED" ]; then
        JENKINS_CONTAINER="$(docker ps -a --filter 'name=jenkins' \
            --format '{{.Names}}' 2>/dev/null | head -1)"
        if [ -n "$JENKINS_CONTAINER" ]; then
            echo "   starting container $JENKINS_CONTAINER..."
            docker start "$JENKINS_CONTAINER" >/dev/null 2>&1 || true
            JENKINS_STARTED="docker:$JENKINS_CONTAINER"
        fi
    fi

    # 3. A jenkins.war sitting in the usual places.
    if [ -z "$JENKINS_STARTED" ]; then
        for war in "$HOME/jenkins.war" "$HOME/Downloads/jenkins.war" \
                   /usr/local/opt/jenkins/libexec/jenkins.war \
                   /opt/homebrew/opt/jenkins/libexec/jenkins.war \
                   /opt/homebrew/opt/jenkins-lts/libexec/jenkins.war
        do
            if [ -f "$war" ]; then
                echo "   starting $war with java..."
                mkdir -p logs
                nohup java -jar "$war" --httpPort=8080 > logs/jenkins.log 2>&1 &
                echo $! > logs/jenkins.pid
                JENKINS_STARTED="war:$war"
                break
            fi
        done
    fi

    if [ -n "$JENKINS_STARTED" ]; then
        echo "   waiting for Jenkins to come up (first start can take a minute)..."
        for _ in $(seq 1 60); do
            curl -fsS -o /dev/null http://localhost:8080/login 2>/dev/null && break
            sleep 2
        done
    fi

    if curl -fsS -o /dev/null http://localhost:8080/login 2>/dev/null; then
        ok "Jenkins answering on http://localhost:8080 (via ${JENKINS_STARTED:-unknown})"
    elif [ -n "$JENKINS_STARTED" ]; then
        bad "Started $JENKINS_STARTED but :8080 is not answering yet."
        echo "   Give it another minute, then reload http://localhost:8080"
        [ -f logs/jenkins.log ] && echo "   Log: logs/jenkins.log"
    else
        bad "No Jenkins installation found (brew service, container, or .war)."
        echo "   The app and dashboard below will still come up; only the"
        echo "   pipeline demo needs Jenkins. To install it:"
        echo "       brew install jenkins-lts && brew services start jenkins-lts"
        echo "   Or run the walkthrough from the recorded build in REPORT.md section 8."
    fi
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

cat <<TIP

   Open these three tabs before the evaluator arrives:
     http://localhost:5050    the app
     http://localhost:8501    the dashboard
     http://localhost:8080    Jenkins (the phishguard pipeline job)

   If this script found docker off your PATH, make that permanent:
     echo 'export PATH="$DOCKER_PATH_FIXUP:\$PATH"' >> ~/.zshrc && source ~/.zshrc

   Useful during the demo:
     docker compose ps                 containers + health
     docker images phishguard          the tagged image versions
     docker compose logs -f app        live request log
     ./demo-down.sh                    stop everything afterwards
TIP
