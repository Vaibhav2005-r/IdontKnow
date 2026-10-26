# Recreating the Jenkins job

If Jenkins shows no jobs, recreate the pipeline job from the config in this
folder. This happened once already: Jenkins was upgraded (2.568.3 -> 2.580.1)
and `~/.jenkins/jobs/` came back empty, with nothing to restore from because
the job had only ever existed as clicks in the UI. That is why the config
lives in the repo now.

## This machine's setup (as of Oct 2026)

| | |
|---|---|
| Install | `brew install jenkins-lts`, LaunchAgent `sh.brew.jenkins-lts.plist` |
| Runs as | `vaibhav` (your own user, so it can reach Docker and your files) |
| `JENKINS_HOME` | `~/.jenkins` |
| URL | `http://localhost:8080` (bound to 127.0.0.1) |

## Option 0 — drop the config in and reload (fastest)

```bash
mkdir -p ~/.jenkins/jobs/phishguard
cp jenkins/phishguard-job.xml ~/.jenkins/jobs/phishguard/config.xml
```

Then **Manage Jenkins -> Reload Configuration from Disk**. The job appears
with no restart.

## Option A — the UI

1. **New Item** → name `phishguard` → **Pipeline** → OK
2. Scroll to **Pipeline**:
   - Definition: **Pipeline script from SCM**
   - SCM: **Git**
   - Repository URL: `/Users/vaibhav/PS/phishguard`
     (the local clone — no credentials, works offline. Use the GitHub URL
     only once you are demonstrating the webhook.)
   - Branch Specifier: `*/main`
   - Script Path: `Jenkinsfile`
3. **Save** → **Build Now**

If Jenkins refuses a local path, tick *Manage Jenkins → Security →
Git Host Key Verification → Accept first connection*, or use the GitHub URL.

## Option B — from the XML in this folder

```bash
# one-time: fetch the CLI jar from your running Jenkins
curl -O http://localhost:8080/jnlpJars/jenkins-cli.jar

# create an API token first: Jenkins -> your user -> Configure -> API Token
java -jar jenkins-cli.jar -s http://localhost:8080 -auth <user>:<token> \
    create-job phishguard < jenkins/phishguard-job.xml
```

To update an existing job instead, use `update-job` in place of `create-job`.

## What the build needs on PATH

The Jenkins process runs as your user via brew, or as the `jenkins` user if
installed as a service, and the build shells out to all of these:

| Tool | Used by stage |
|---|---|
| `python3.12` | Setup Python env, Train, Unit tests |
| `docker` | Build image, Selenium tests, Deploy |
| `trivy` | Trivy scan |
| Chrome | Selenium tests |

Jenkins here starts from a **LaunchAgent**, which hands it a minimal
`PATH` (`/usr/bin:/bin:/usr/sbin:/sbin`) regardless of what your shell has.
So `docker`, `trivy` and `python3.12` are all invisible to a build until you
set it explicitly. Do this **before the first build**:

**Manage Jenkins -> System -> Global properties -> Environment variables**

| Name | Value |
|---|---|
| `PATH` | `/opt/homebrew/bin:/usr/local/bin:/Users/vaibhav/.docker/bin:/usr/bin:/bin:/usr/sbin:/sbin` |

A stage dying with "command not found" is nearly always this.

## Plugins

The `Jenkinsfile` deliberately uses only `sh`, `junit` and
`archiveArtifacts` — no `readJSON`, no `docker.` DSL — so it needs nothing
beyond the standard pipeline and git plugins. The gate is read from
`ml/train.py`'s exit code in a `sh(returnStatus: true)`, not parsed from
JSON, which is one less plugin to depend on.

One optional plugin is worth having for a demo: **Pipeline: Stage View**
draws the stage-by-stage diagram. Without it builds still run, but you only
get console output — much less convincing to show someone.

## First run

The first build pulls a Python base image and installs dependencies, so it
takes a few minutes. Later builds reuse the Docker layer cache and finish in
around two and a half minutes.
