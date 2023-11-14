pipeline{
    agent any

    environment {
        DJANGO_SETTINGS_MODULE="LearnEasyAI.settings"
        APP_NAME = "django_test"
        RELEASE = "1.0.0"
        DOCKER_USER = "siddharthgopalpatel"
        DOCKER_PASS = 'dockerhub'
        IMAGE_NAME = "${DOCKER_USER}" + "/" + "${APP_NAME}"
        IMAGE_TAG = "${RELEASE}-${BUILD_NUMBER}"
        OPENAI_API_KEY='siddnidhi'
    }

    stages{
        stage("Cleanup Workspace"){
            steps {
                cleanWs()
            }
        }

        stage("Checkout from SCM"){
            steps {
               git branch: 'master', credentialsId: 'github', url: 'https://github.com/siddharthpatel1993/dcp_devsecops'
            }
        }

        stage("Initial Test") {
            steps {
                script {
                        sh "python3 -m pip install -r requirements.txt"
                        sh "python3 -m pytest --cov --cov-report=xml"
                }
            }
        }

        stage("Sonarqube Analysis") {
            steps {
                script {
                    withSonarQubeEnv(credentialsId: 'jenkins_sonarqube_token') {
                        sh "/opt/sonar-scanner/bin/sonar-scanner -Dsonar.projectKey=test -Dsonar.sources=. -Dsonar.host.url=http://44.210.123.179 -Dsonar.python.coverage.reportPaths=coverage.xml -Dsonar.python.version=3 -Dsonar.projectVersion=${BUILD_NUMBER}"
                    }
                }
            }

        }

        stage("Quality Gate") {
            steps {
                script {
                    waitForQualityGate abortPipeline: false, credentialsId: 'jenkins_sonarqube_token'
                }
            }

        }

        stage("Build & Push Docker Image") {
            steps {
                script {
                    docker.withRegistry('',DOCKER_PASS) {
                        docker_image = docker.build "${IMAGE_NAME}"
                    }

                    docker.withRegistry('',DOCKER_PASS) {
                        docker_image.push("${IMAGE_TAG}")
                        docker_image.push('latest')
                    }
                }
            }

        }

        stage("Trivy Scan") {
            steps {
                script {
                   sh ('docker run -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image siddharthgopalpatel/django_test:${IMAGE_TAG} --no-progress --scanners vuln  --exit-code 0 --severity HIGH,CRITICAL --format table')
                }
            }

        }

        stage("Excecute ansible") {
            steps {
                script {
                   ansiblePlaybook installation: 'test', inventory: 'inventory', playbook: 'test.yml'
                }
            }

        }
      stage ('Cleanup Artifacts') {
            steps {
                script {
                    sh "docker rmi ${IMAGE_NAME}:${IMAGE_TAG}"
                    sh "docker rmi ${IMAGE_NAME}:latest"
                }
            }
        }
     }

    post {
        failure {
            emailext body: '''${SCRIPT, template="groovy-html.template"}''', 
                    subject: "${env.JOB_NAME} - Build # ${env.BUILD_NUMBER} - Failed", 
                    mimeType: 'text/html',to: "siddharthgopal825@gmail.com"
            }
         success {
               emailext body: '''${SCRIPT, template="groovy-html.template"}''', 
                    subject: "${env.JOB_NAME} - Build # ${env.BUILD_NUMBER} - Successful", 
                    mimeType: 'text/html',to: "siddharthgopal825@gmail.com"
          }     

    }
}
