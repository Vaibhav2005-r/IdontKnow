# Recreating the Jenkins job

If Jenkins shows no jobs (fresh install, cleared `JENKINS_HOME`, or a
different instance than the one used before), recreate the pipeline job.
It takes about two minutes.

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

A stage failing with "command not found" almost always means Jenkins has a
narrower `PATH` than your shell. Fix it in **Manage Jenkins → System →
Global properties → Environment variables**, adding `PATH` with
`/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`.

## First run

The first build pulls a Python base image and installs dependencies, so it
takes a few minutes. Later builds reuse the Docker layer cache and finish in
around two and a half minutes.
