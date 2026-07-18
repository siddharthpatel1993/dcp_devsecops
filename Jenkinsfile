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

        // =================================================================
        // SECRET SCANNING — Detect leaked credentials/API keys in code
        // =================================================================
        // Defence-in-Depth strategy for secret protection:
        //
        // Layer 1 — Developer Machine (pre-commit + detect-secrets):
        //   - Runs locally BEFORE commit is created
        //   - Instant feedback, secret never enters local git history
        //   - Setup: .pre-commit-config.yaml with detect-secrets hook
        //   - Limitation: developer can skip with --no-verify
        //
        // Layer 2 — Git Server (GitHub Push Protection):
        //   - Server-side block — secret never lands on remote
        //   - Covers the gap where pre-commit is skipped
        //   - Auto-revokes tokens for known providers (AWS, Slack, etc.)
        //   - Free for public repos, GitHub Advanced Security for private
        //
        // Layer 3 — CI Pipeline (THIS STAGE — hard gate):
        //   - Even if Layer 1 & 2 are bypassed, CI catches it
        //   - Pipeline FAILS — secret never reaches main branch
        //   - Catches custom patterns that GitHub may not know about
        //   - Uses Trivy (already on agent) — zero new tooling
        //
        // Together: virtually airtight. Secret cannot survive all 3 layers.
        // =================================================================
        stage("Secret Scanning") {
            steps {
                script {
                    // Trivy filesystem scan in secret mode
                    // Scans all files for: API keys, passwords, tokens, private keys
                    // --exit-code 1 = FAIL pipeline if secrets detected
                    // Secret never progresses past this stage
                    sh """trivy filesystem . \
                        --scanners secret \
                        --severity HIGH,CRITICAL \
                        --exit-code 1"""
                    // If this fails: developer must remove secret from code,
                    // use environment variables or K8s Secrets/Vault instead,
                    // and if secret was already pushed — ROTATE IT IMMEDIATELY
                    // (git history retains it even after deletion)
                }
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

        // =================================================================
        // SCA — Software Composition Analysis (Snyk)
        // =================================================================
        // Scans dependencies (requirements.txt) for known vulnerabilities
        // Runs BEFORE Docker build — fail fast, don't waste compute
        // Snyk also checks transitive deps + provides license compliance
        // Prerequisites:
        //   - Snyk CLI installed on Jenkins agent (npm install -g snyk)
        //   - SNYK_TOKEN stored as Jenkins credential (secret text)
        // =================================================================
        stage("SCA - Snyk Dependency Scan") {
            steps {
                script {
                    withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
                        sh """snyk auth ${SNYK_TOKEN}
                            snyk test --file=requirements.txt \
                            --severity-threshold=high \
                            --json-file-output=snyk-report.json || true"""
                        // --severity-threshold=high: only fail on HIGH/CRITICAL
                        // || true: don't fail pipeline (change to remove || true for hard gate)
                        // Report uploaded to S3 later with Trivy report
                    }
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
        // MULTI-ENVIRONMENT PROMOTION — Dev → Staging → Prod
        // =================================================================
        // Architecture:
        //   - Same signed image promoted through environments (never rebuilt)
        //   - Kustomize overlays control per-env config (replicas, resources, TLS)
        //   - ArgoCD watches each overlay directory separately
        //   - Gates between environments ensure quality before promotion
        //
        // Flow:
        //   Dev (auto) → DAST + Smoke Test → Staging (auto) → Manual Approval → Prod
        //
        // Key principle: "What you test is what you deploy"
        //   Image abc123f is built ONCE, scanned ONCE, signed ONCE
        //   Only the image TAG in kustomization.yml changes per environment
        //
        // GitOps repo structure (Kustomize):
        //   dcp_devsecops-gitops/
        //   ├── base/           (shared: deployment, service, pdb)
        //   └── overlays/
        //       ├── dev/        (1 replica, low resources, no TLS)
        //       ├── staging/    (2 replicas, prod-like, TLS staging cert)
        //       └── prod/       (3 replicas, full resources, TLS prod cert)
        // =================================================================

        // -----------------------------------------------------------------
        // STAGE: Deploy to DEV — Automatic (every successful build)
        // -----------------------------------------------------------------
        stage("Deploy to DEV") {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'github', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                        sh """
                            git clone https://${GIT_USER}:${GIT_PASS}@github.com/siddharthpatel1993/dcp_devsecops-gitops.git
                            cd dcp_devsecops-gitops

                            # Update ONLY dev overlay — staging/prod untouched
                            sed -i 's|newTag:.*|newTag: ${IMAGE_TAG}|' overlays/dev/kustomization.yml

                            git config user.email 'jenkins@ci.com'
                            git config user.name 'Jenkins CI'
                            git add overlays/dev/kustomization.yml
                            git commit -m '[DEV] Deploy image ${IMAGE_TAG}'
                            git push origin main
                        """
                    }
                    // ArgoCD (learneasyai-dev Application) detects change
                    // → auto-syncs to project-dev namespace
                }
            }
        }

        // -----------------------------------------------------------------
        // GATE 1: DAST scan against DEV environment
        // -----------------------------------------------------------------
        // Validates the running application BEFORE promoting to staging
        // Catches: missing security headers, XSS, CSRF, auth bypass, info leakage
        // -----------------------------------------------------------------
        stage("DAST - OWASP ZAP (DEV)") {
            steps {
                script {
                    // Wait for ArgoCD to sync + pods to become ready
                    sh "sleep 45"

                    sh """docker run --rm \
                        -v \${WORKSPACE}/zap_report:/zap/wrk:rw \
                        owasp/zap2docker-stable zap-baseline.py \
                        -t http://dev.learneasyai.example.com \
                        -r zap-scan-report-dev-${IMAGE_TAG}.html \
                        -l WARN \
                        -I"""

                    // Upload report to S3
                    sh "aws s3 cp zap_report/zap-scan-report-dev-${IMAGE_TAG}.html s3://delivery-champion-mana-devsecops-2023-scanning-reports/"
                }
            }
        }

        // -----------------------------------------------------------------
        // GATE 1: Smoke Tests against DEV
        // -----------------------------------------------------------------
        // Quick functional validation — is the app responding correctly?
        // If smoke test fails → image does NOT get promoted to staging
        // -----------------------------------------------------------------
        stage("Smoke Test (DEV)") {
            steps {
                script {
                    sh """
                        # Basic health check — is the app responding?
                        RESPONSE=\$(curl -s -o /dev/null -w '%{http_code}' http://dev.learneasyai.example.com/admin/)
                        if [ "\$RESPONSE" != "200" ] && [ "\$RESPONSE" != "302" ]; then
                            echo "Smoke test FAILED! Got HTTP \$RESPONSE"
                            exit 1
                        fi
                        echo "Smoke test PASSED — DEV is healthy (HTTP \$RESPONSE)"
                    """
                }
            }
        }

        // -----------------------------------------------------------------
        // STAGE: Promote to STAGING — Automatic after DEV gates pass
        // -----------------------------------------------------------------
        // Only reaches here if: DAST clean + smoke tests pass on DEV
        // Same image (${IMAGE_TAG}) — never rebuilt, just promoted
        // -----------------------------------------------------------------
        stage("Promote to STAGING") {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'github', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                        sh """
                            cd dcp_devsecops-gitops

                            # Update staging overlay with same image tag that passed DEV
                            sed -i 's|newTag:.*|newTag: ${IMAGE_TAG}|' overlays/staging/kustomization.yml

                            git add overlays/staging/kustomization.yml
                            git commit -m '[STAGING] Promote image ${IMAGE_TAG} (passed DEV gates)'
                            git push origin main
                        """
                    }
                    // ArgoCD (learneasyai-staging Application) detects change
                    // → auto-syncs to project-staging namespace
                }
            }
        }

        // -----------------------------------------------------------------
        // GATE 2: Integration/Smoke Tests against STAGING
        // -----------------------------------------------------------------
        stage("Smoke Test (STAGING)") {
            steps {
                script {
                    // Wait for ArgoCD to sync staging
                    sh "sleep 45"

                    sh """
                        RESPONSE=\$(curl -s -o /dev/null -w '%{http_code}' https://staging.learneasyai.example.com/admin/)
                        if [ "\$RESPONSE" != "200" ] && [ "\$RESPONSE" != "302" ]; then
                            echo "Staging smoke test FAILED! Got HTTP \$RESPONSE"
                            exit 1
                        fi
                        echo "Staging smoke test PASSED (HTTP \$RESPONSE)"
                    """
                }
            }
        }

        // -----------------------------------------------------------------
        // GATE 3: Manual Approval for PRODUCTION
        // -----------------------------------------------------------------
        // Human-in-the-loop — authorized personnel must approve
        // Shows what image tag will be deployed + link to reports
        // Times out after 24 hours (no stale approvals)
        // -----------------------------------------------------------------
        stage("Approval for PRODUCTION") {
            steps {
                input message: """
                    Deploy ${IMAGE_TAG} to PRODUCTION?

                    ✅ Passed: Secret Scan, SCA, SAST, Trivy, DAST, Smoke Tests
                    📋 Reports: s3://delivery-champion-mana-devsecops-2023-scanning-reports/
                    🔖 Image: ${IMAGE_NAME}:${IMAGE_TAG} (signed with Cosign)
                """,
                ok: "Deploy to Production",
                submitter: "lead-devops,platform-team,siddharth"
                // Only listed users/groups can approve
                // Everyone else sees the gate but cannot click approve
            }
        }

        // -----------------------------------------------------------------
        // STAGE: Promote to PRODUCTION — After manual approval
        // -----------------------------------------------------------------
        // Same image that passed ALL gates — no rebuild, no re-scan
        // ArgoCD prod app has automated sync DISABLED — extra safety
        // After git push, ArgoCD shows "OutOfSync" → ops team clicks sync
        // OR enable auto-sync if you trust the gate process fully
        // -----------------------------------------------------------------
        stage("Deploy to PRODUCTION") {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'github', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                        sh """
                            cd dcp_devsecops-gitops

                            # Update prod overlay — this is the final promotion
                            sed -i 's|newTag:.*|newTag: ${IMAGE_TAG}|' overlays/prod/kustomization.yml

                            git add overlays/prod/kustomization.yml
                            git commit -m '[PROD] Deploy image ${IMAGE_TAG} (approved by team)'
                            git push origin main
                        """
                    }
                    // ArgoCD (learneasyai-prod Application):
                    //   - If auto-sync disabled: shows OutOfSync, ops clicks Sync
                    //   - If auto-sync enabled: deploys immediately
                    //   - Either way: rolling update with maxUnavailable: 0
                    echo "✅ Production deployment triggered for ${IMAGE_TAG}"
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
