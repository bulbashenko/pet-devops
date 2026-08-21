// Release pipeline.
//
// Division of labour: GitHub Actions gates pull requests, this pipeline cuts
// releases — it is the side that has the Artifactory credentials and can reach
// the deploy target. See docs/adr/0001-gha-gates-jenkins-releases.md.
//
// Every stage shells out to a `make` target. The same commands run on a
// developer's laptop, which is what makes a red build reproducible locally.

pipeline {
    agent { label 'ubuntu-build' }

    options {
        timestamps()
        ansiColor('xterm')
        timeout(time: 45, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    environment {
        PATH = "/opt/toolchain/bin:${env.PATH}"
        CONAN_HOME = "/home/jenkins/.conan2"
        LC_ALL = 'C.UTF-8'
        LANG = 'C.UTF-8'
    }

    stages {
        stage('Version') {
            steps {
                script {
                    // One version, derived from the git tag, carried by the
                    // Conan package, the .deb, the wheel and the image alike.
                    env.PROJECT_VERSION = sh(
                        script: './scripts/version.sh',
                        returnStdout: true,
                    ).trim()
                    currentBuild.displayName = "#${env.BUILD_NUMBER} — ${env.PROJECT_VERSION}"
                }
                sh 'make version'
            }
        }

        stage('Build') {
            steps {
                sh 'make build'
            }
        }

        stage('Test') {
            steps {
                sh 'make test'
            }
            post {
                always {
                    junit testResults: 'reports/*.xml', allowEmptyResults: false
                }
            }
        }

        stage('Package') {
            steps {
                sh 'make package'
            }
            post {
                success {
                    archiveArtifacts artifacts: 'dist/*', fingerprint: true
                }
            }
        }

        stage('Publish') {
            steps {
                script {
                    // Credentials are optional on purpose: a local run of this
                    // stack has no Artifactory, and that must not be a failure.
                    def artifactoryUrl = credentialsAvailable('artifactory-url')
                    if (!artifactoryUrl) {
                        echo 'No Artifactory credentials configured — skipping publish.'
                        return
                    }

                    withCredentials([
                        usernamePassword(credentialsId: 'artifactory',
                                         usernameVariable: 'JFROG_USER',
                                         passwordVariable: 'JFROG_TOKEN'),
                        string(credentialsId: 'artifactory-url', variable: 'JFROG_URL'),
                        string(credentialsId: 'conan-remote-url', variable: 'CONAN_REMOTE_URL'),
                    ]) {
                        sh 'make publish'
                    }
                }
            }
        }

        stage('Deploy') {
            when {
                expression { return !params.SKIP_DEPLOY }
            }
            steps {
                sshagent(credentials: ['deploy-key']) {
                    script {
                        if (params.DEPLOY_SOURCE == 'artifactory') {
                            withCredentials([
                                usernamePassword(credentialsId: 'artifactory',
                                                 usernameVariable: 'JFROG_USER',
                                                 passwordVariable: 'JFROG_TOKEN'),
                                string(credentialsId: 'artifactory-url', variable: 'JFROG_URL'),
                            ]) {
                                sh 'SOURCE=artifactory make deploy'
                            }
                        } else {
                            sh 'SOURCE=local make deploy'
                        }
                    }
                }
            }
        }

        stage('Smoke test') {
            when {
                expression { return !params.SKIP_DEPLOY }
            }
            steps {
                // Verifies the deployed instance serves the version this build
                // produced — not merely that something is listening.
                sh """
                    ./scripts/smoke_test.py \
                        --endpoint http://target-host:8080 \
                        --expect-version '${env.PROJECT_VERSION}'
                """
            }
        }
    }

    post {
        success {
            echo "sensor-hub ${env.PROJECT_VERSION} built, packaged and verified."
        }
        failure {
            echo "Release of ${env.PROJECT_VERSION ?: 'unknown version'} failed at stage ${env.STAGE_NAME}."
        }
        cleanup {
            cleanWs(notFailBuild: true)
        }
    }
}

// Returns the secret text of a credential, or null when it is absent or blank.
// Jenkins throws if you bind a credential that does not exist, so the pipeline
// has to look before it binds.
String credentialsAvailable(String credentialsId) {
    try {
        String value = null
        withCredentials([string(credentialsId: credentialsId, variable: 'PROBE')]) {
            value = env.PROBE
        }
        return value?.trim() ? value : null
    } catch (ignored) {
        return null
    }
}
