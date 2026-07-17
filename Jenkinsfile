pipeline{
    agent any

    environment {
        DJANGO_SETTINGS_MODULE="LearnEasyAI.settings"
        APP_NAME = "dcp_devsecops"
        RELEASE = "1.0.0"
        DOCKER_USER = "siddharthgopalpatel"
        DOCKER_PASS = 'dockerhub'
        IMAGE_NAME = "${DOCKER_USER}" + "/" + "${APP_NAME}"
        // =========================================================================
        // IMAGE_TAG: Using git commit SHA instead of RELEASE-BUILD_NUMBER
        // Why: 
        //   - "latest" is mutable — you can't tell which code is running
        //   - BUILD_NUMBER resets if Jenkins is rebuilt
        //   - Git SHA = EXACT code traceability. Given any running container,
        //     you can instantly trace back to the exact commit
        //   - Immutable — same SHA always means same code
        // Old: IMAGE_TAG = "${RELEASE}-${BUILD_NUMBER}"  (e.g., 1.0.0-45)
        // New: IMAGE_TAG = git short SHA (e.g., a3f7b2c)
        // =========================================================================
        IMAGE_TAG = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
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


        // =================================================================
        // STAGE ORDER FIX: Build → Scan → Push
        // 
        // OLD order: Build → Push → Scan (WRONG!)
        //   Problem: vulnerable image is already in registry before scan runs
        //   Even if scan fails, the bad image is already pushed and pullable
        //
        // NEW order: Build → Scan → Push (CORRECT!)
        //   - Build locally (image exists only on Jenkins agent)
        //   - Trivy scans LOCAL image (not from registry)
        //   - Only if scan PASSES → push to registry
        //   - Result: vulnerable images NEVER reach registry at all
        // =================================================================

        stage("Build Docker Image") {
            steps {
                script {
                    // Build image locally — NOT pushed yet
                    // Image exists only on this Jenkins agent until scan passes
                    docker.withRegistry('',DOCKER_PASS) {
                        docker_image = docker.build "${IMAGE_NAME}:${IMAGE_TAG}"
                    }
                }
            }
        }

        stage("Trivy Image Scan") {
            steps {
                script {
                    // Scan the LOCAL image BEFORE pushing to registry
                    // --exit-code 1 = FAIL the pipeline if HIGH/CRITICAL found
                    // This is the gate — vulnerable image dies here, never reaches registry
                    sh "mkdir -p trivy_report"
                    sh """trivy image ${IMAGE_NAME}:${IMAGE_TAG} \
                        --no-progress \
                        --scanners vuln \
                        --severity HIGH,CRITICAL \
                        --exit-code 1 \
                        --format template \
                        --template "@/usr/local/share/trivy/templates/html.tpl" \
                        -o trivy_report/trivy-image-scanning-report-${IMAGE_TAG}.html"""
                    // Note: --exit-code 1 means pipeline STOPS here if vulnerabilities found
                    // Image never gets pushed. Developer must fix CVE and rebuild.
                }
            }
        }

        stage("Push Docker Image") {
            steps {
                script {
                    // Only reaches here if Trivy scan PASSED (no HIGH/CRITICAL)
                    // Now safe to push — this image is verified clean
                    docker.withRegistry('',DOCKER_PASS) {
                        docker_image.push("${IMAGE_TAG}")
                    }
                }
            }
        }

        // =================================================================
        // IMAGE SIGNING WITH COSIGN
        // =================================================================
        // Why sign images?
        //   - Without signing: anyone can push a malicious image to registry
        //     with same tag, and K8s will happily run it. No proof of origin.
        //   - With signing: CI/CD pipeline stamps a cryptographic signature
        //     on the image. Like a tamper-proof seal on a food delivery bag.
        //   - Kyverno policy in K8s cluster REJECTS any unsigned image.
        //   - Result: only images that passed our pipeline can run in cluster.
        //
        // What it prevents:
        //   - Registry compromise (attacker replaces image) → no signature → rejected
        //   - Rogue developer pushes directly to registry → no signature → rejected
        //   - Old unscanned image deployed → was never signed → rejected
        //
        // Prerequisites:
        //   - cosign installed on Jenkins agent
        //   - COSIGN_PRIVATE_KEY stored as Jenkins credential (file type)
        //   - Kyverno installed in K8s cluster with verify-image policy
        // =================================================================
        stage("Sign Image with Cosign") {
            steps {
                script {
                    // Sign the pushed image with our private key
                    // This attaches a signature to the image in the registry
                    // Anyone can VERIFY with the public key, but only CI/CD can SIGN
                    withCredentials([file(credentialsId: 'cosign-private-key', variable: 'COSIGN_KEY')]) {
                        sh """cosign sign --key ${COSIGN_KEY} \
                            --yes \
                            ${IMAGE_NAME}:${IMAGE_TAG}"""
                    }
                    // After this: image in registry has a cryptographic signature
                    // Kyverno in cluster will verify this before allowing deployment
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


        // =================================================================
        // GITOPS DEPLOYMENT — Update image tag in Git, ArgoCD does the rest
        // =================================================================
        // OLD method (Ansible):
        //   Jenkins → SSH to K8s master → kubectl delete → kubectl apply
        //   Problems: needs SSH, imperative, delete causes downtime, no audit
        //
        // NEW method (GitOps):
        //   Jenkins → updates image tag in Git repo → DONE
        //   ArgoCD (inside cluster) → watches Git → detects change → rolling update
        //
        // Why GitOps is better:
        //   - No SSH/kubectl access needed from Jenkins (security)
        //   - Git = single source of truth (what's in Git = what's in cluster)
        //   - Drift detection: manual kubectl change → ArgoCD auto-reverts
        //   - Rollback = git revert (not scramble to find old config)
        //   - Audit trail = git log (who changed what, when, reviewable)
        //   - Works across multiple clusters (just add destination)
        //
        // How it works:
        //   1. Jenkins updates image tag in GitOps repo (sed command)
        //   2. Git push triggers ArgoCD (webhook or 3-min poll)
        //   3. ArgoCD compares Git (desired) vs Cluster (actual)
        //   4. ArgoCD applies diff with rolling update (maxUnavailable: 0)
        //   5. Zero-downtime — new pods ready before old ones killed
        // =================================================================
        stage("Update GitOps Repo") {
            steps {
                script {
                    // Clone the GitOps repo that ArgoCD watches
                    // This repo ONLY contains K8s manifests (not app code)
                    // Separation of concerns: app repo ≠ deployment config repo
                    withCredentials([usernamePassword(credentialsId: 'github', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                        sh """
                            git clone https://${GIT_USER}:${GIT_PASS}@github.com/siddharthpatel1993/dcp_devsecops-gitops.git
                            cd dcp_devsecops-gitops

                            # Update image tag to new git SHA
                            # This is the ONLY thing Jenkins does for deployment
                            # sed replaces the old image tag with new one
                            sed -i 's|image: siddharthgopalpatel/dcp_devsecops:.*|image: siddharthgopalpatel/dcp_devsecops:${IMAGE_TAG}|' k8s.yml

                            # Commit and push — this triggers ArgoCD
                            git config user.email 'jenkins@ci.com'
                            git config user.name 'Jenkins CI'
                            git add k8s.yml
                            git commit -m 'Deploy: update image to ${IMAGE_TAG}'
                            git push origin main
                        """
                    }
                    // Jenkins is DONE. It never touches the cluster.
                    // ArgoCD (running inside cluster) will:
                    //   1. Detect this new commit
                    //   2. Compare with current cluster state
                    //   3. Apply rolling update (zero-downtime)
                    //   4. Report health status in ArgoCD UI
                }
            }
        }

        // =================================================================
        // DAST — Dynamic Application Security Testing (OWASP ZAP)
        // =================================================================
        // What is DAST?
        //   - Tests the RUNNING application from outside (like an attacker would)
        //   - Sends real HTTP requests, tries common attacks, checks responses
        //   - Black-box testing — doesn't need source code, tests the live app
        //
        // Why DAST when we already have SAST (SonarQube)?
        //   - SAST scans CODE (finds hardcoded secrets, SQL injection patterns)
        //   - DAST scans the RUNNING APP (finds what SAST can't):
        //     • Missing security headers (CSP, X-Frame-Options, HSTS)
        //     • Misconfigured CORS (allows any origin)
        //     • Auth bypass (broken session management)
        //     • XSS that only appears at runtime
        //     • Server info leakage (expose Django debug=True, stack traces)
        //     • CSRF vulnerabilities
        //     • Cookie without Secure/HttpOnly flags
        //
        // When in pipeline?
        //   - AFTER deployment (app must be running to test it)
        //   - Against staging/dev URL (never scan production — it's noisy)
        //   - Generates HTML report → stored in S3 for security team
        //
        // Why OWASP ZAP?
        //   - Free, open-source, industry standard
        //   - Docker image available (no install needed)
        //   - Baseline scan (quick, passive) vs Full scan (slow, active attacks)
        //   - Generates standardized reports
        // =================================================================
        stage("DAST - OWASP ZAP Scan") {
            steps {
                script {
                    // Wait for deployment to be ready (pods running, passing readiness)
                    sh "sleep 30"

                    // Run ZAP baseline scan against the deployed application
                    // Baseline scan = passive (safe, fast, ~2 min)
                    //   - Spiders the app, checks responses for security issues
                    //   - Does NOT actively attack (safe for shared environments)
                    // Full scan = active (slow, ~30 min, sends attack payloads)
                    //   - Use on dedicated staging only
                    sh """docker run --rm \
                        -v \${WORKSPACE}/zap_report:/zap/wrk:rw \
                        owasp/zap2docker-stable zap-baseline.py \
                        -t http://app.example.com \
                        -r zap-scan-report-${IMAGE_TAG}.html \
                        -l WARN \
                        -I"""
                    // Flags explained:
                    //   -t = target URL (replace with your staging URL)
                    //   -r = HTML report filename
                    //   -l WARN = only report WARN and above (filter noise)
                    //   -I = don't fail on warnings (fail only on HIGH alerts)
                    //        Remove -I to make pipeline fail on any finding

                    // Upload ZAP report to S3 alongside Trivy report
                    sh "aws s3 cp zap_report/zap-scan-report-${IMAGE_TAG}.html s3://delivery-champion-mana-devsecops-2023-scanning-reports/"
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
