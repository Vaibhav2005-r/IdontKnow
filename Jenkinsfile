// PhishGuard pipeline. Stage names are written for the Blue Ocean view to
// tell the whole MLOps story: data -> gate -> tests -> image -> UI tests ->
// scan -> deploy. Triggered by a GitHub webhook push and a nightly cron.
pipeline {
    agent any

    triggers {
        githubPush()
        cron('H 2 * * *')
    }

    environment {
        DATA_PATH            = 'data/raw/phishing_urls.csv'
        FEEDBACK_DB_PATH     = 'data/feedback/feedback.db'
        MODEL_REGISTRY_PATH  = 'models/registry.json'
        LAST_RUN_PATH        = 'artifacts/last_run.json'
        IMAGE_NAME           = 'phishguard'
        TEST_CONTAINER       = 'phishguard-selenium-test'
        TEST_PORT            = '5057'
        GATE_REJECTED        = 'false'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Python env') {
            steps {
                sh '''
                    python3.12 -m venv .venv || python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip -q
                    pip install -q -r requirements-dev.txt
                '''
            }
        }

        stage('Merge feedback + Train') {
            steps {
                // The live app's feedback.db lives in a Docker named volume, not this
                // workspace -- pull it in first or every retrain only ever sees the
                // committed dataset, never what users actually corrected.
                sh '''
                    mkdir -p data/feedback
                    docker cp phishguard-app:/app/data/feedback/feedback.db data/feedback/feedback.db 2>/dev/null || \
                        echo "No running phishguard-app container (or no feedback yet) -- training on committed data only."
                '''
                script {
                    def feedbackArg = fileExists(env.FEEDBACK_DB_PATH) ? "--feedback ${env.FEEDBACK_DB_PATH}" : ''
                    def trainStatus = sh(
                        script: """
                            . .venv/bin/activate
                            python -m ml.train --data ${env.DATA_PATH} ${feedbackArg}
                        """,
                        returnStatus: true
                    )
                    if (trainStatus == 2) {
                        env.GATE_REJECTED = 'true'
                        currentBuild.result = 'UNSTABLE'
                        echo 'Accuracy gate rejected the candidate model -- skipping build & deploy.'
                    } else if (trainStatus != 0) {
                        error("ml.train failed with exit code ${trainStatus}")
                    }
                }
            }
        }

        stage('Accuracy gate') {
            steps {
                sh '''
                    echo "---- artifacts/last_run.json ----"
                    cat artifacts/last_run.json || true
                '''
                script {
                    if (env.GATE_REJECTED == 'true') {
                        echo 'Gate: REJECTED (see artifacts/last_run.json). Build marked UNSTABLE.'
                    } else {
                        echo 'Gate: PROMOTED.'
                    }
                }
            }
        }

        stage('Unit tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    mkdir -p artifacts
                    pytest -m "not ui" --junitxml=artifacts/pytest-results.xml
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'artifacts/pytest-results.xml'
                }
            }
        }

        stage('Build image') {
            when { expression { env.GATE_REJECTED != 'true' } }
            steps {
                script {
                    def version = sh(
                        script: "python3 -c \"import json; print(json.load(open('${env.MODEL_REGISTRY_PATH}'))['live_version'])\"",
                        returnStdout: true
                    ).trim()
                    env.MODEL_VERSION = version
                    sh """
                        docker build -t ${env.IMAGE_NAME}:${version} -t ${env.IMAGE_NAME}:latest .
                    """
                }
            }
        }

        stage('Selenium tests against built container') {
            when { expression { env.GATE_REJECTED != 'true' } }
            steps {
                sh """
                    docker rm -f ${env.TEST_CONTAINER} 2>/dev/null || true
                    docker run -d --rm --name ${env.TEST_CONTAINER} -p ${env.TEST_PORT}:5000 ${env.IMAGE_NAME}:${env.MODEL_VERSION}
                """
                sh '''
                    for i in $(seq 1 20); do
                        curl -sf http://localhost:${TEST_PORT}/health && break
                        sleep 2
                    done
                '''
                sh '''
                    . .venv/bin/activate
                    APP_BASE_URL=http://localhost:${TEST_PORT} pytest tests/ui -m ui --junitxml=artifacts/selenium-results.xml
                '''
            }
            post {
                always {
                    sh "docker rm -f ${env.TEST_CONTAINER} 2>/dev/null || true"
                    junit allowEmptyResults: true, testResults: 'artifacts/selenium-results.xml'
                }
            }
        }

        stage('Trivy scan') {
            when { expression { env.GATE_REJECTED != 'true' } }
            steps {
                sh """
                    trivy image --exit-code 0 --severity HIGH,CRITICAL \
                        --format table --output artifacts/trivy-report.txt \
                        ${env.IMAGE_NAME}:${env.MODEL_VERSION} || true
                    cat artifacts/trivy-report.txt || true
                """
            }
        }

        stage('Deploy') {
            when { expression { env.GATE_REJECTED != 'true' } }
            steps {
                sh '''
                    docker compose up -d --build
                '''
            }
        }

        stage('Archive artifacts') {
            steps {
                archiveArtifacts artifacts: 'artifacts/**, models/registry.json', allowEmptyArchive: true, fingerprint: true
            }
        }
    }

    post {
        unstable {
            echo 'Build finished UNSTABLE: candidate model rejected by the accuracy gate. Live model unchanged.'
        }
        failure {
            echo 'Build FAILED. Check the stage logs above.'
        }
        success {
            echo "Build finished. Live model version: ${env.MODEL_VERSION ?: 'unchanged'}"
        }
    }
}
