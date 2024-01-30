pipeline{
    agent any

    environment {
        DJANGO_SETTINGS_MODULE="LearnEasyAI.settings"
        APP_NAME = "dcp_devsecops"
        RELEASE = "1.0.0"
        DOCKER_USER = "siddharthgopalpatel"
        DOCKER_PASS = 'dockerhub'
        IMAGE_NAME = "${DOCKER_USER}" + "/" + "${APP_NAME}"
        IMAGE_TAG = "${RELEASE}-${BUILD_NUMBER}"
        OPENAI_API_KEY='apikey'
    }

    options {
        buildDiscarder logRotator( 
                    daysToKeepStr: '1', 
                    numToKeepStr: '1'
            )
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

        stage("Unit Test") {
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
                        sh "/opt/sonar-scanner/bin/sonar-scanner -Dsonar.projectKey=project_devops -Dsonar.sources=. -Dsonar.host.url=http://3.86.31.123 -Dsonar.python.coverage.reportPaths=coverage.xml -Dsonar.python.version=3 -Dsonar.projectVersion=${BUILD_NUMBER}"
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


        stage("Trivy Image Scan") {
            steps {
                script {
                   sh "mkdir trivy_report"
                   //sh ('docker run -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image siddharthgopalpatel/dcp_devsecops:${IMAGE_TAG} --no-progress --scanners vuln --exit-code 0 --severity HIGH,CRITICAL --format table')
                   sh ('trivy image siddharthgopalpatel/dcp_devsecops:${IMAGE_TAG} --no-progress --scanners vuln --severity HIGH,CRITICAL --format template --template "@/usr/local/share/trivy/templates/html.tpl" -o trivy_report/trivy-image-scanning-report${BUILD_NUMBER}.html')
                }
            }

        }

        stage("Sending Scan Report to AWS S3 Bucket") {
            steps {
                script {
                    sh "aws s3 sync trivy_report/ s3://delivery-champion-mana-devsecops-2023-scanning-reports"
                }
            }
        }


        stage("Deployment using ansible") {
            steps {
                script {
                   ansiblePlaybook installation: 'test', inventory: 'inventory', playbook: 'test.yml'
                }
            }

        }

      //stage ('Cleanup Artifacts') {
      //      steps {
      //          script {
      //              sh "docker rmi ${IMAGE_NAME}:${IMAGE_TAG}"
      //              sh "docker rmi ${IMAGE_NAME}:latest"
      //              sh "docker rm -f \$(docker ps -a -q)"
      //              sh "docker rmi -f \$(docker images -q)"
      //          }
      //      }
      //  }

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
