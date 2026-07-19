<div align="center">

# 🔒 DevSecOps CI/CD Pipeline
## AI Learning Platform — Complete Project Documentation

**Author:** Siddharth Patel  
**GitHub:** [siddharthpatel1993/dcp_devsecops](https://github.com/siddharthpatel1993/dcp_devsecops)  
**Pipeline Maturity:** Level 5 — Platform Grade  
**Pipeline Stages:** 18 | **Security Layers:** 6 | **Environments:** 3

---

</div>

## 📋 Table of Contents

| # | Section | Page |
|---|---------|------|
| 1 | [Project Overview](#1-project-overview) | 2 |
| 2 | [Application Details](#2-application-details) | 3 |
| 3 | [Architecture & Flow](#3-architecture--flow) | 4 |
| 4 | [Pipeline Stages (18)](#4-pipeline-stages) | 5 |
| 5 | [Security Implementation (6 Layers)](#5-security-implementation) | 11 |
| 6 | [Kubernetes Deployment](#6-kubernetes-deployment) | 15 |
| 7 | [GitOps with ArgoCD](#7-gitops-with-argocd) | 18 |
| 8 | [Multi-Environment Promotion](#8-multi-environment-promotion) | 20 |
| 9 | [Canary Deployment & Auto-Rollback](#9-canary-deployment--auto-rollback) | 22 |
| 10 | [Observability Stack](#10-observability-stack) | 25 |
| 11 | [Design Decisions](#11-design-decisions) | 27 |
| 12 | [Interview Quick Reference](#12-interview-quick-reference) | 29 |
| 13 | [CI/CD Pipeline for VMs — Container vs VM Comparison](#13-cicd-pipeline-for-vms--container-vs-vm-comparison) | 31 |
| 14 | [CI vs Continuous Delivery vs Continuous Deployment](#14-ci-vs-continuous-delivery-vs-continuous-deployment) | 34 |
| 15 | [Multi-Language Pipeline Strategy](#15-multi-language-pipeline-strategy) | 37 |

---

## 1. Project Overview

### Problem Statement

Needed an end-to-end DevSecOps pipeline for a Django-based AI learning application with security integrated at every stage — from code commit to canary production deployment on Kubernetes.

### What This Project Demonstrates

- **18-stage Jenkins pipeline** with security gates at every level
- **6 layers of defence in depth** — secrets, SCA, SAST, container, supply chain, runtime
- **Multi-environment promotion** — Dev → Staging → Prod with automated + manual gates
- **Canary deployments** — gradual traffic shift (5% → 100%) with auto-rollback
- **Observability-driven decisions** — Prometheus metrics gate canary promotion
- **GitOps** — ArgoCD, drift detection, git-based rollback
- **CI/CD platform built from scratch** — Docker Compose: Jenkins + SonarQube + custom agent

### CI/CD Platform Infrastructure

Built the entire DevSecOps environment from scratch:

- **Docker Compose stack:** Jenkins Master + Custom Agent + SonarQube
- **Custom Jenkins Agent:** Ubuntu + SSH + Sonar Scanner 5.0.1 + Trivy + Java JDK
- **install.bash** — bare-metal alternative for non-Docker setups
- **Result:** Entire environment reproducible in <5 minutes

---

## 2. Application Details

**LearnEasyAI** — Django web app that generates learning content from YouTube videos.

| Component | Detail |
|-----------|--------|
| Framework | Django 4.2 |
| AI Engine | OpenAI GPT-3.5-turbo |
| Video Processing | YouTube Transcript API |
| Server | Gunicorn (3 workers, port 8000) |
| Database | SQLite (dev) — would be PostgreSQL/RDS in prod |
| Features | YouTube → Notes, AI Chatbot Tutor |

**Key dependencies** (`requirements.txt`):
```
Django==4.2.2
youtube-transcript-api==0.6.1
openai==0.27.8
python-decouple==3.8
gunicorn==20.1.0
pytest, pytest-django, pytest-cov
```

---

## 3. Architecture & Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE PIPELINE FLOW                            │
│                                                                         │
│  Developer → Git Push → Jenkins (18 Stages)                             │
│                                                                         │
│  BUILD PHASE:                                                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ Secret  │→│  Unit   │→│  SCA    │→│  SAST   │→│ Quality │        │
│  │  Scan   │ │  Tests  │ │ (Snyk)  │ │(Sonar)  │ │  Gate   │        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
│                                                                         │
│  PACKAGE PHASE:                                                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ Docker  │→│  Trivy  │→│  Push   │→│ Cosign  │→│   S3    │        │
│  │  Build  │ │  Scan   │ │ (clean) │ │  Sign   │ │ Reports │        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
│                                                                         │
│  DEPLOY PHASE:                                                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ Deploy  │→│ DAST +  │→│Promote  │→│ Manual  │→│ Deploy  │        │
│  │  DEV    │ │ Smoke   │ │STAGING  │ │Approval │ │  PROD   │        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
│                                                         │               │
│                                                         ▼               │
│                                          Canary: 5%→20%→50%→80%→100%   │
│                                          Prometheus checks at each step │
│                                          FAIL → Auto-rollback           │
└─────────────────────────────────────────────────────────────────────────┘
```


---

## 4. Pipeline Stages

### Stage 1: Cleanup Workspace

Wipes the Jenkins workspace clean before every build. Prevents stale files from previous builds causing issues.

```groovy
stage("Cleanup Workspace") {
    steps { cleanWs() }
}
```

### Stage 2: Checkout from SCM

Pulls the latest code from GitHub.

```groovy
stage("Checkout from SCM") {
    steps {
        git branch: 'master', credentialsId: 'github',
            url: 'https://github.com/siddharthpatel1993/dcp_devsecops'
    }
}
```

### Stage 3: Secret Scanning 🔐

**What:** Scans every file for leaked API keys, passwords, tokens, private keys.  
**Why:** If a developer accidentally commits credentials, catch it BEFORE anything else runs.  
**Gate:** Pipeline FAILS immediately — nothing else wastes compute.

```groovy
stage("Secret Scanning") {
    steps {
        script {
            sh """trivy filesystem . \
                --scanners secret \
                --severity HIGH,CRITICAL \
                --exit-code 1"""
        }
    }
}
```

**Defence in depth for secrets:**
- Layer 1: Pre-commit hooks (detect-secrets) — developer machine
- Layer 2: GitHub Push Protection — server blocks the push
- Layer 3: This CI stage — hard gate, catches what others miss

### Stage 4: Unit Tests

Runs pytest with coverage reporting. Catches bugs in application logic.

```groovy
stage("Unit Test") {
    steps {
        script {
            sh "python3 -m pip install -r requirements.txt"
            sh "python3 -m pytest --cov --cov-report=xml"
        }
    }
}
```

Coverage report (`coverage.xml`) is later consumed by SonarQube.

### Stage 5: SCA — Software Composition Analysis (Snyk)

**What:** Scans your dependencies for known vulnerabilities.  
**Why:** Even if YOUR code is perfect, Django 4.2.2 might have a CVE. Catches it before Docker build.

```groovy
stage("SCA - Snyk Dependency Scan") {
    steps {
        script {
            withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
                sh """snyk auth ${SNYK_TOKEN}
                    snyk test --file=requirements.txt \
                    --severity-threshold=high \
                    --json-file-output=snyk-report.json || true"""
            }
        }
    }
}
```

### Stage 6: SAST — SonarQube Analysis

**What:** Reads your source code and finds security bugs without running the app.  
**Catches:** SQL injection patterns, XSS, hardcoded credentials, code smells.

```groovy
stage("Sonarqube Analysis") {
    steps {
        script {
            withSonarQubeEnv(credentialsId: 'jenkins_sonarqube_token') {
                sh """/opt/sonar-scanner/bin/sonar-scanner \
                    -Dsonar.projectKey=project_devops \
                    -Dsonar.sources=. \
                    -Dsonar.python.coverage.reportPaths=coverage.xml \
                    -Dsonar.python.version=3"""
            }
        }
    }
}
```

### Stage 7: Quality Gate

SonarQube evaluates thresholds: "Are there critical bugs? Is coverage below target?"  
If thresholds are breached → pipeline can stop.

```groovy
stage("Quality Gate") {
    steps {
        script {
            waitForQualityGate abortPipeline: false, credentialsId: 'jenkins_sonarqube_token'
        }
    }
}
```

### Stage 8: Build Docker Image

Multi-stage build — builder stage installs deps, production stage copies only the installed packages. Result: 900MB → 150MB, no build tools in production.

```groovy
stage("Build Docker Image") {
    steps {
        script {
            docker.withRegistry('', DOCKER_PASS) {
                docker_image = docker.build "${IMAGE_NAME}:${IMAGE_TAG}"
            }
        }
    }
}
```

**Dockerfile highlights:**
```dockerfile
# Stage 1: Builder
FROM python:3.9-slim AS builder
RUN apt-get update && apt-get install -y gcc
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Production (no gcc, no pip, no build tools)
FROM python:3.9-slim
COPY --from=builder /root/.local /root/.local
COPY . .
ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "LearnEasyAI.wsgi"]
```

### Stage 9: Trivy Image Scan (BEFORE Push)

**Critical design:** Scan happens BEFORE pushing to registry. If vulnerabilities found, image never leaves the build agent.

```groovy
stage("Trivy Image Scan") {
    steps {
        script {
            sh """trivy image ${IMAGE_NAME}:${IMAGE_TAG} \
                --scanners vuln \
                --severity HIGH,CRITICAL \
                --exit-code 1 \
                --format template \
                --template "@/usr/local/share/trivy/templates/html.tpl" \
                -o trivy_report/trivy-image-scanning-report-${IMAGE_TAG}.html"""
        }
    }
}
```

`--exit-code 1` = pipeline STOPS. Developer must fix the CVE and rebuild.


### Stage 10: Push Docker Image

Only reaches here if Trivy scan PASSED. Pushes with Git-SHA tag (never `:latest`).

```groovy
stage("Push Docker Image") {
    steps {
        script {
            docker.withRegistry('', DOCKER_PASS) {
                docker_image.push("${IMAGE_TAG}")  // e.g., a3f7b2c
            }
        }
    }
}
```

**Why Git-SHA?** `:latest` is mutable — you can't trace what's running. SHA = exact commit = exact code.

### Stage 11: Sign Image (Cosign)

Stamps a cryptographic signature on the image. Like a tamper-proof seal.

```groovy
stage("Sign Image with Cosign") {
    steps {
        script {
            withCredentials([file(credentialsId: 'cosign-private-key', variable: 'COSIGN_KEY')]) {
                sh "cosign sign --key ${COSIGN_KEY} --yes ${IMAGE_NAME}:${IMAGE_TAG}"
            }
        }
    }
}
```

Kyverno in the cluster verifies this signature before allowing the pod to run.

### Stage 12: S3 Report Upload

Stores Trivy HTML report in S3 for audit/compliance. Security team can review anytime.

```groovy
stage("Sending Scan Report to AWS S3 Bucket") {
    steps {
        script {
            sh "aws s3 sync trivy_report/ s3://devsecops-scanning-reports"
        }
    }
}
```

### Stage 13: Deploy to DEV (Auto)

Updates the image tag in the DEV overlay of the GitOps repo. ArgoCD auto-syncs.

```groovy
stage("Deploy to DEV") {
    steps {
        script {
            withCredentials([usernamePassword(credentialsId: 'github', ...)]) {
                sh """
                    git clone https://github.com/.../dcp_devsecops-gitops.git
                    cd dcp_devsecops-gitops
                    sed -i 's|newTag:.*|newTag: ${IMAGE_TAG}|' overlays/dev/kustomization.yml
                    git commit -am '[DEV] Deploy image ${IMAGE_TAG}'
                    git push origin main
                """
            }
        }
    }
}
```

### Stage 14: DAST — OWASP ZAP (DEV)

Tests the RUNNING application from outside — like an attacker would.

```groovy
stage("DAST - OWASP ZAP (DEV)") {
    steps {
        script {
            sh "sleep 45"  // Wait for ArgoCD sync + pods ready
            sh """docker run --rm owasp/zap2docker-stable zap-baseline.py \
                -t http://dev.learneasyai.example.com \
                -r zap-scan-report-dev-${IMAGE_TAG}.html -l WARN -I"""
            sh "aws s3 cp zap_report/... s3://devsecops-scanning-reports/"
        }
    }
}
```

**Finds:** Missing security headers, XSS, CSRF, info leakage, broken auth — things SAST can't detect.

### Stage 15: Smoke Test (DEV)

Quick functional check — is the app actually responding?

```groovy
stage("Smoke Test (DEV)") {
    steps {
        script {
            sh """
                RESPONSE=\$(curl -s -o /dev/null -w '%{http_code}' http://dev.learneasyai.example.com/admin/)
                if [ "\$RESPONSE" != "200" ] && [ "\$RESPONSE" != "302" ]; then
                    echo "Smoke test FAILED!"; exit 1
                fi
            """
        }
    }
}
```

### Stage 16: Promote to STAGING

Same image — just updates the staging overlay. No rebuild, no re-scan.

```groovy
stage("Promote to STAGING") {
    steps {
        script {
            sh """
                cd dcp_devsecops-gitops
                sed -i 's|newTag:.*|newTag: ${IMAGE_TAG}|' overlays/staging/kustomization.yml
                git commit -am '[STAGING] Promote image ${IMAGE_TAG}'
                git push origin main
            """
        }
    }
}
```

### Stage 17: Smoke Test (STAGING)

Same check against staging URL — validates prod-like config works.

### Stage 18: Deploy to PRODUCTION (Manual Approval + Canary)

Human-in-the-loop gate. Only authorized team members can approve.

```groovy
stage("Approval for PRODUCTION") {
    steps {
        input message: "Deploy ${IMAGE_TAG} to PRODUCTION?",
              ok: "Deploy to Production",
              submitter: "lead-devops,platform-team,siddharth"
    }
}

stage("Deploy to PRODUCTION") {
    steps {
        script {
            sh """
                cd dcp_devsecops-gitops
                sed -i 's|newTag:.*|newTag: ${IMAGE_TAG}|' overlays/prod/kustomization.yml
                git commit -am '[PROD] Deploy image ${IMAGE_TAG}'
                git push origin main
            """
        }
    }
}
```

After this, Argo Rollouts takes over with canary strategy (5% → 100%).

---

## 5. Security Implementation — Complete Breakdown

Every security mechanism in this project explained in detail:

### 6 Layers of Defence in Depth

```
┌──────────────────────────────────────────────────────────┐
│  Layer 1: SECRETS       → Trivy secret scan (CI gate)    │
│  Layer 2: DEPENDENCIES  → Snyk SCA                       │
│  Layer 3: CODE          → SonarQube SAST + Quality Gate  │
│  Layer 4: CONTAINER     → Trivy image scan (before push) │
│  Layer 5: SUPPLY CHAIN  → Cosign + Kyverno admission     │
│  Layer 6: RUNTIME       → ZAP DAST + Canary + Alerts     │
└──────────────────────────────────────────────────────────┘
```

> **One-liner:** Pipeline catches secrets (scanning), bad dependencies (SCA), code bugs (SAST), container CVEs (Trivy), tampered images (Cosign+Kyverno), and runtime vulns (DAST) — covering the full lifecycle from commit to production.

---

### 1. Secret Scanning (Stage 3)

**What:** Finds hardcoded passwords, API keys, tokens in your code.

**How it works:** Trivy scans every file using regex patterns + entropy analysis (high-randomness strings that look like keys). If found → pipeline fails.

**Tool used:** Trivy (filesystem mode, `--scanners secret`)

**Alternatives:** GitLeaks, TruffleHog, detect-secrets, GitHub Secret Scanning

**Defence in depth for secrets:**

| Layer | Tool | When | Limitation |
|-------|------|------|-----------|
| Developer machine | pre-commit + detect-secrets | Before commit | Can skip with `--no-verify` |
| Git server | GitHub Push Protection | Before push lands | Only known provider patterns |
| CI Pipeline (THIS) | Trivy filesystem | After checkout | Hard gate — cannot bypass |

**If secret already leaked:** Rotate immediately → BFG Repo-Cleaner to purge from history → Force push → Everyone re-clones.

---

### 2. Unit Testing + Code Coverage (Stage 4)

**What:** Verifies your application logic works correctly.

**How it works:** pytest runs test functions, hits your Django endpoints, checks response codes. Coverage report shows % of code exercised by tests.

**Tool used:** pytest + pytest-cov

**Alternatives:** unittest (built-in), nose2, tox

**Example test from the project:**
```python
from django.test import Client

def test_one():
    client = Client()
    response = client.get('/input')
    assert response.status_code == 200

def test_fourth():
    client = Client()
    response = client.get('/notes')
    assert response.status_code == 301
```

Coverage report (`coverage.xml`) is consumed by SonarQube for Quality Gate evaluation.

---

### 3. SCA — Software Composition Analysis (Stage 5)

**What:** Finds known vulnerabilities in your dependencies (Django, openai, gunicorn, etc.)

**How it works:** Snyk reads `requirements.txt`, checks each package + its transitive deps against vulnerability databases (NVD, Snyk DB). Flags HIGH/CRITICAL CVEs.

**Tool used:** Snyk

**Alternatives:** Trivy filesystem, pip-audit, OWASP Dependency-Check, Grype

**Why it matters:** Even if YOUR code is perfect, if Django 4.2.2 has a known CVE, attackers can exploit it. SCA catches this before you even build the Docker image.

**Transitive dependencies:** Your app uses `openai` which depends on `requests` which depends on `urllib3`. SCA checks ALL of them — not just what's in your requirements.txt.

---

### 4. SAST — Static Application Security Testing (Stage 6)

**What:** Finds security bugs in YOUR code without running it.

**How it works:** SonarQube parses your Python source code, builds an AST (abstract syntax tree), applies rules to detect: SQL injection patterns, XSS, hardcoded creds, code smells, bugs. Also ingests coverage report.

**Tool used:** SonarQube + Sonar Scanner

**Alternatives:** Bandit (Python-specific), Semgrep, Checkmarx, Fortify, CodeQL

**What it catches:**
- SQL injection patterns (string concatenation in queries)
- XSS (unescaped user input in templates)
- Hardcoded credentials (password = "admin123")
- Code smells (unused variables, duplicate code)
- Bug patterns (null references, unreachable code)

---

### 5. Quality Gate (Stage 7)

**What:** Pass/fail decision based on thresholds.

**How it works:** SonarQube evaluates: "Are there >0 critical bugs? Is coverage below 80%? Are there new vulnerabilities?" If any condition fails → gate fails → pipeline can stop.

**Tool used:** SonarQube Quality Gate (built-in)

**Alternatives:** Custom script checking thresholds, Sonar + webhook

**Typical thresholds:**
- Zero critical or blocker bugs
- Zero new vulnerabilities
- Coverage above 80% on new code
- Duplication below 3%

---

### 6. Multi-stage Docker Build (Stage 8)

**What:** Reduces attack surface by shipping only runtime — no build tools.

**How it works:** Stage 1 installs gcc + pip packages. Stage 2 copies ONLY the installed packages into a clean slim image. Result: no compiler, no pip, no source of build tools for attacker to exploit. 900MB → 150MB.

**Tool used:** Docker multi-stage builds

**Alternatives:** Distroless images (Google), Alpine-based builds, scratch images (for Go/Rust)

**Why it matters for security:**
- Attacker compromises container → finds no gcc, no wget, no curl
- Fewer packages = fewer CVEs in Trivy scan
- Smaller image = faster deploys + less storage cost

---

### 7. Container Vulnerability Scan (Stage 9)

**What:** Finds CVEs in OS packages + Python libs inside the built image.

**How it works:** Trivy pulls the image's layer manifest, reads installed packages (apt + pip), cross-references against vuln DBs. `--exit-code 1` on HIGH/CRITICAL = pipeline fails. Image never reaches registry.

**Tool used:** Trivy (image mode)

**Alternatives:** Grype, Snyk Container, Clair, AWS ECR scanning, Docker Scout

**Critical design:** Scan happens BEFORE `docker push`. Old pipelines pushed first, then scanned — meaning the vulnerable image was already pullable from registry. Here, it never leaves the build agent.

---

### 8. Image Signing — Supply Chain Security (Stage 11)

**What:** Proves this image was built by your CI/CD — not tampered with.

**How it works:** Cosign uses a private key (in Jenkins) to generate a cryptographic signature and attaches it to the image in registry. Like a wax seal — if broken, you know it's been tampered.

**Tool used:** Cosign (Sigstore project)

**Alternatives:** Docker Content Trust (Notary), AWS Signer, in-toto

**What it prevents:**
- Registry compromise (attacker replaces image) → no valid signature → rejected
- Rogue developer pushes directly to registry → unsigned → rejected
- Old unscanned image deployed → was never signed → rejected

---

### 9. Admission Control — Kyverno Policy (Cluster)

**What:** Kubernetes rejects any unsigned or untrusted image at deploy time.

**How it works:** Kyverno runs as an admission webhook. When a pod is created, Kyverno intercepts → checks if image has valid Cosign signature using the public key → if no/invalid → pod rejected. Also restricts to only your registry prefix.

**Tool used:** Kyverno

**Alternatives:** OPA Gatekeeper, Sigstore Policy Controller, Connaisseur

```yaml
# Kyverno ClusterPolicy
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signature
spec:
  validationFailureAction: enforce    # Block (not just audit)
  rules:
    - name: verify-cosign-signature
      match:
        resources:
          kinds: [Pod]
          namespaces: [project]
      verifyImages:
      - imageReferences: ["siddharthgopalpatel/dcp_devsecops:*"]
        attestors:
        - entries:
          - keys:
              publicKeys: |-
                -----BEGIN PUBLIC KEY-----
                (your cosign.pub content here)
                -----END PUBLIC KEY-----
```

**Bonus policy:** `restrict-image-registries` — blocks ALL images except from `siddharthgopalpatel/` prefix. Prevents pulling random Docker Hub images (supply chain risk).

---

### 10. DAST — Dynamic Application Security Testing (Stage 14)

**What:** Attacks your running application like a hacker would.

**How it works:** OWASP ZAP spiders the deployed app, sends malicious payloads (XSS, injection, header manipulation), checks responses for vulnerabilities. Finds things SAST can't: missing security headers, CSRF issues, session problems, server info leakage.

**Tool used:** OWASP ZAP (baseline scan)

**Alternatives:** Burp Suite (enterprise), Nuclei, Nikto, Acunetix

**What DAST catches that SAST cannot:**
- Missing security headers (CSP, X-Frame-Options, HSTS)
- Misconfigured CORS (allows any origin)
- Auth bypass (broken session management)
- XSS that only appears at runtime
- Server info leakage (Django debug=True, stack traces)
- Cookie without Secure/HttpOnly flags

**Baseline vs Full scan:**
- Baseline (used here): passive, safe, ~2 min. Spiders app, checks responses.
- Full scan: active attacks, ~30 min. Sends real payloads. Use only on dedicated staging.

---

### 11. Git-SHA Image Tags (Pipeline-wide)

**What:** Every image is tagged with exact commit hash — never `:latest`.

**How it works:** `git rev-parse --short HEAD` = immutable tag. Given any running container, you trace back to exact code. `:latest` is mutable — you never know what's running.

**Tool used:** Git + pipeline logic

**Alternatives:** Semantic versioning with commit suffix, digest-based references

**Why `:latest` is dangerous:**
- Same tag can point to different images at different times
- No traceability — which code is running in production?
- BUILD_NUMBER resets if Jenkins is rebuilt
- Git SHA = exact code commit. Always. Forever.

---

### 12. Kubernetes Hardening (Deployment)

**What:** Probes, resource limits, PDB — production resilience + security.

**How it works:**

| Control | What it does | Security benefit |
|---------|-------------|-----------------|
| Readiness probe | Removes unhealthy pod from traffic | Users never hit broken pods |
| Liveness probe | Restarts hung/deadlocked pods | Auto-recovery from crashes |
| Resource limits | Cap CPU/memory per pod | Prevents DoS from inside (noisy neighbor) |
| PDB | Guarantees min pods during maintenance | Availability during node drains |
| ClusterIP + Ingress | No direct pod exposure | Encrypted traffic (TLS), hidden infra |

**Tools used:** Native Kubernetes + Nginx Ingress + cert-manager

**Alternatives:** Istio (mTLS), Linkerd, Traefik, AWS ALB Ingress

---

### 13. GitOps — ArgoCD (Deployment)

**What:** Git is the single source of truth. Nobody touches the cluster directly.

**How it works:** Jenkins updates image tag in Git → ArgoCD detects → syncs to cluster. `selfHeal: true` means any manual kubectl change gets auto-reverted. Rollback = `git revert`.

**Tool used:** ArgoCD

**Alternatives:** Flux CD, Rancher Fleet, Harness GitOps

**Security benefit:** Jenkins NEVER has kubectl/SSH access to the cluster. Attack surface reduced — compromising Jenkins doesn't give cluster access.

---

### 14. Audit Trail (S3 Reports)

**What:** Compliance evidence — who scanned what, when, what was found.

**How it works:** Trivy HTML report + ZAP report uploaded to S3 with image tag in filename. Auditor can trace: this image → this scan result → this deployment commit.

**Tool used:** AWS S3

**Alternatives:** Elasticsearch, DefectDojo (centralized vuln management), Nexus IQ dashboard

**Compliance value:** For SOC2/ISO27001 audits — demonstrate that every production image was scanned and the results are retained. Git history provides deployment audit trail (who deployed what, when, approved by whom).


---

## 6. Kubernetes Deployment

### Production Setup Summary

| Resource | Config | Purpose |
|----------|--------|---------|
| Deployment/Rollout | 3 replicas | HA, zero-downtime deploys |
| Strategy | maxSurge:1, maxUnavailable:0 | New pod ready before old killed |
| Readiness Probe | httpGet /admin/ every 5s | Remove unhealthy from traffic |
| Liveness Probe | httpGet /admin/ every 10s | Restart deadlocked pods |
| Resources | requests + limits | Prevent noisy neighbor |
| Service | ClusterIP | Internal only, Ingress handles external |
| Ingress | Nginx + TLS (cert-manager) | HTTPS, domain routing |
| PDB | minAvailable: 2 | Safe node maintenance |
| Kyverno | Reject unsigned images | Supply chain enforcement |

### Probes Explained

```yaml
# Readiness: "Can this pod serve traffic?"
readinessProbe:
  httpGet:
    path: /admin/
    port: 8000
  initialDelaySeconds: 10    # Wait for app startup
  periodSeconds: 5           # Check every 5s
  failureThreshold: 3        # 3 failures = mark unready (no traffic)

# Liveness: "Is this pod alive or stuck?"
livenessProbe:
  httpGet:
    path: /admin/
    port: 8000
  initialDelaySeconds: 30    # Longer wait (avoid killing during startup)
  periodSeconds: 10
  failureThreshold: 3        # 3 failures = restart container
```

### Resources Per Environment

| Environment | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-------------|-------------|-----------|----------------|--------------|
| DEV | 50m | 200m | 128Mi | 256Mi |
| STAGING | 100m | 500m | 256Mi | 512Mi |
| PROD | 200m | 1 core | 512Mi | 1Gi |

### Why ClusterIP + Ingress (not NodePort)

| NodePort | ClusterIP + Ingress |
|----------|-------------------|
| Exposes node IP:30000 | Single LB, hidden nodes |
| No TLS | Auto-renewed Let's Encrypt |
| Ugly URL | Real domain name |
| One port per service | Path-based routing |

### Ingress with TLS

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: learneasyai-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts: [learneasyai.example.com]
    secretName: learneasyai-tls
  rules:
  - host: learneasyai.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service: { name: learneasyai-service, port: { number: 8000 } }
```

### What Makes This Production-Ready ✅

| Feature | Why it matters |
|---------|---------------|
| 3 replicas | Survives node failure, enables zero-downtime deploys |
| Rolling update (maxUnavailable: 0) | No downtime during deploys — old pod serves until new one is healthy |
| Readiness + Liveness probes | Traffic only goes to healthy pods, stuck pods auto-restart |
| Resource requests + limits | Scheduler places pods correctly, prevents noisy neighbor, enables HPA |
| PDB (minAvailable: 2) | Safe node drains during maintenance — K8s won't kill all pods |
| ClusterIP + Ingress (not NodePort) | Proper production pattern — TLS, domain routing, no exposed node IPs |
| TLS via cert-manager + Let's Encrypt | Auto-provisioned, auto-renewed HTTPS — zero manual cert management |
| Kyverno admission policies | Only signed images from trusted registry can run |
| ArgoCD with selfHeal + prune | Drift protection, declarative deployments, git-based rollback |
| Git-SHA tags | Immutable, traceable — you always know what's running |

### Minor Gaps (Mention as "Future Improvements" in Interviews)

| Gap | Production Impact | Fix |
|-----|-------------------|-----|
| Probes hitting `/admin/` | Works but not ideal — admin page is heavier, may have auth redirects | Add dedicated `/health/` endpoint (lightweight, no DB hit) |
| No HPA (Horizontal Pod Autoscaler) | Fixed 3 replicas — can't handle traffic spikes | Add HPA based on CPU/memory or custom metrics |
| No NetworkPolicy | Any pod in cluster can talk to your pods | Add NetworkPolicy to allow only Ingress → app traffic |
| SQLite in image | Not suitable for multi-replica (each pod has its own DB) | External PostgreSQL/RDS with K8s Secret for connection |
| No non-root user | Container runs as root — wider blast radius if exploited | Uncomment USER 1001 + fix permissions |
| No external secrets management | Secrets created manually via kubectl | External Secrets Operator + AWS Secrets Manager/Vault |
| No Pod Security Standards/Admission | No enforcement of seccomp, privilege escalation prevention | Apply `restricted` Pod Security Standard |

**Bottom line:** This is a solid production setup. It covers the top concerns: **availability** (replicas + PDB + rolling update), **security** (TLS + Kyverno + probes), and **operability** (ArgoCD + resource limits). The gaps are real-world hardening steps you'd do in a mature platform — and knowing them shows depth in interviews.

---

### K8s vs OpenShift — What Changes?

Core concepts stay the same, but OpenShift has its own opinions and built-in alternatives.

**What works as-is (no change needed):**

| Resource | OpenShift Behaviour |
|----------|-------------------|
| Deployment (3 replicas, rolling update) | Works identically — same API |
| Service (ClusterIP) | Works identically — same API |
| ConfigMaps / Secrets | Works identically — same API |
| PDB (PodDisruptionBudget) | Works identically — same API |
| Resource requests/limits | Works identically — same API |
| Readiness/Liveness probes | Works identically — same API |
| ArgoCD | Works on OpenShift — widely used combo |

**What needs to change or gets replaced:**

| K8s Resource | OpenShift Equivalent | Why |
|--------------|---------------------|-----|
| Ingress + Nginx Ingress Controller | **Route** (built-in) | OpenShift has its own router (HAProxy-based). `oc expose svc` creates a Route with TLS automatically. |
| cert-manager + ClusterIssuer | **Route with edge TLS** | OpenShift router handles TLS natively. cert-manager still works but many teams use built-in cert rotation. |
| Kyverno (admission policy) | **Built-in Image Signature Verification + OPA Gatekeeper** | OpenShift 4.x has native image signature verification via `policy.json`. |
| Non-root user (commented out) | **Enforced by default** | OpenShift runs containers as random non-root UID (SCC). Your Dockerfile MUST work without root. |
| Pod Security Standards | **SCC (Security Context Constraints)** | Default `restricted` SCC blocks root, privileged, host network. |
| Namespace | **Project** | Same concept, different name. `oc new-project` instead of `kubectl create namespace`. |
| Docker build in pipeline | **BuildConfig (S2I)** | OpenShift has built-in build system. But since Jenkins builds externally, your flow still works. |

**Key differences that will bite you:**

1. **Non-root enforcement (biggest one):**
```dockerfile
# Your Dockerfile currently runs as root
# OpenShift will FAIL with permission denied on:
#   - /var/log/gunicorn (root-owned directory)
#   - /var/run/gunicorn
# Fix: chown to 1001 and uncomment USER 1001
```

2. **Ingress → Route:**
```yaml
# OpenShift Route (native replacement for Ingress)
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: learneasyai
spec:
  to:
    kind: Service
    name: learneasyai-service
  port:
    targetPort: 8000
  tls:
    termination: edge    # OpenShift router handles TLS
```

3. **Image pull policy:** OpenShift has stricter policies + built-in registry. May need to allow Docker Hub explicitly or mirror images.

**Summary:**

| Concern | K8s (your setup) | OpenShift |
|---------|-----------------|-----------|
| External traffic | Nginx Ingress + cert-manager | Route (built-in, TLS included) |
| Security enforcement | Kyverno + manual hardening | SCC + built-in image verification |
| Container user | Optional (you skipped it) | Mandatory non-root |
| Pod security | Pod Security Admission | SCC (more mature) |
| Build system | External (Jenkins) | Can use external or built-in S2I |
| GitOps | ArgoCD | ArgoCD (same) |
| Core workloads | Deployment, Service, PDB | Same APIs — no change |

**Bottom line:** ~70% of your manifests work unchanged. Main adjustments: Ingress → Route, fix non-root user (mandatory), and image signature policy moves to OpenShift-native. Core architecture (ArgoCD + Jenkins + Deployments + probes) stays identical.

---

## 7. GitOps with ArgoCD

### Old vs New Deployment Method

| Old (Ansible) | New (GitOps) |
|---------------|-------------|
| Jenkins → SSH → kubectl delete → apply | Jenkins → Git push → ArgoCD syncs |
| Needs SSH access to cluster | Jenkins never touches cluster |
| Delete causes downtime | Rolling update = zero downtime |
| No audit trail | Git log = who deployed what, when |
| Manual rollback (scramble) | git revert → ArgoCD syncs previous |
| No drift detection | selfHeal auto-reverts kubectl changes |

### How It Works

1. Jenkins updates image tag in GitOps repo (`sed` + `git push`)
2. ArgoCD detects new commit (webhook or 3-min poll)
3. ArgoCD compares Git (desired) vs Cluster (actual)
4. ArgoCD applies diff → rolling update / canary
5. Zero-downtime — new pods ready before old ones killed

### ArgoCD Application (simplified)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: learneasyai-prod
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/.../dcp_devsecops-gitops.git
    targetRevision: main
    path: overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: project-prod
  syncPolicy:
    # PROD = manual sync (extra safety)
    # automated:
    #   prune: true
    #   selfHeal: true
```

### Key Features

- **selfHeal: true** — someone does `kubectl edit` → ArgoCD reverts within 3 min
- **prune: true** — resource removed from Git → deleted from cluster (no orphans)
- **Rollback** — `git revert <commit>` → ArgoCD syncs previous state
- **Multi-cluster** — same repo, multiple ArgoCD instances pointing at different clusters

---

## 8. Multi-Environment Promotion

### Concept

Code doesn't go directly to production. It flows through environments with approval/validation gates between each.

### Complete Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  Developer Push                                                                 │
│       │                                                                         │
│       ▼                                                                         │
│  ┌──────────────────────────────────────────────┐                              │
│  │         JENKINS (Build + Security)            │                              │
│  │  Secret Scan → Tests → SCA → SAST → Docker   │                              │
│  │  → Trivy → Push → Cosign → S3 Reports        │                              │
│  └──────────────────────┬───────────────────────┘                              │
│                         │                                                       │
│                         │ Same signed image (abc123f)                           │
│                         │ promoted through environments                         │
│                         ▼                                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐      │
│  │                        GITOPS REPO STRUCTURE                          │      │
│  │                                                                       │      │
│  │   dcp_devsecops-gitops/                                              │      │
│  │   ├── base/                                                           │      │
│  │   │   └── kustomization.yml  (shared config)                          │      │
│  │   └── overlays/                                                       │      │
│  │       ├── dev/                                                        │      │
│  │       │   └── kustomization.yml  (image: abc123f) ← auto-deploy     │      │
│  │       ├── staging/                                                    │      │
│  │       │   └── kustomization.yml  (image: abc123f) ← after dev gates │      │
│  │       └── prod/                                                       │      │
│  │           └── kustomization.yml  (image: abc123f) ← manual approval │      │
│  └──────────────────────────────────────────────────────────────────────┘      │
│                                                                                 │
│                         │              │              │                          │
│                         ▼              ▼              ▼                          │
│                   ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│                   │   DEV    │   │ STAGING  │   │   PROD   │                  │
│                   │ Cluster/ │   │ Cluster/ │   │ Cluster/ │                  │
│                   │Namespace │   │Namespace │   │Namespace │                  │
│                   └──────────┘   └──────────┘   └──────────┘                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Promotion Gates Between Environments

```
     DEV                         STAGING                       PROD
┌────────────┐              ┌────────────┐              ┌────────────┐
│            │              │            │              │            │
│ Auto-deploy│   GATE 1     │ Deploy     │   GATE 2     │ Deploy     │
│ on every   │─────────────▶│ validated  │─────────────▶│ final      │
│ commit     │              │ build      │              │ release    │
│            │              │            │              │            │
└────────────┘              └────────────┘              └────────────┘
                 │                            │
                 ▼                            ▼
         ┌──────────────┐            ┌──────────────────┐
         │ Automated:   │            │ Manual/Policy:   │
         │ • Smoke tests│            │ • Manual approval│
         │   pass       │            │   (PR review)    │
         │ • DAST clean │            │ • Change window  │
         │ • No P1 bugs │            │ • Canary healthy │
         │ • Integration│            │ • SLA check      │
         │   tests pass │            │ • Rollback plan  │
         └──────────────┘            └──────────────────┘
```

### Jenkinsfile Deployment Flow

```
Build + Scan + Sign → Deploy to DEV (auto)
                        │
                    GATE 1: DAST + Smoke Test on DEV
                        │
                    Promote to STAGING (auto)
                        │
                    GATE 2: Smoke Test on STAGING
                        │
                    GATE 3: Manual Approval (authorized team only)
                        │
                    Deploy to PRODUCTION (Canary)
```

### Key Principle

**Same image, different config.** Image `abc123f` is built ONCE, scanned ONCE, signed ONCE — then promoted unchanged through dev → staging → prod. Only environment-specific config (replicas, domains, secrets, feature flags) differs via Kustomize overlays.

This ensures what you tested is exactly what runs in production — no "works on staging but not prod" surprises.

### Kustomize Structure

```
gitops/
├── base/                          ← Shared resources
│   ├── deployment.yml             (pod spec, probes, volumes)
│   ├── service.yml                (ClusterIP)
│   ├── pdb.yml                    (PodDisruptionBudget)
│   └── kustomization.yml
└── overlays/
    ├── dev/                       ← 1 replica, low resources, auto-deploy
    │   └── kustomization.yml
    ├── staging/                   ← 2 replicas, TLS, auto after gates
    │   ├── kustomization.yml
    │   └── ingress.yml
    └── prod/                      ← 3 replicas, canary, manual approval
        ├── kustomization.yml
        ├── rollout.yml            (Argo Rollout)
        ├── analysis-template.yml  (Prometheus gates)
        └── ingress.yml
```

### Dev Overlay Example

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: project-dev
resources:
  - ../../base
images:
  - name: siddharthgopalpatel/dcp_devsecops
    newTag: IMAGE_TAG_PLACEHOLDER    # Updated by Jenkins
patches:
  - target: { kind: Deployment, name: learneasyai }
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 1
```

### Key Design Decisions

- **Same image** promoted through all envs (never rebuilt)
- **DEV:** fully automated — fast feedback for developers
- **STAGING:** automated after DEV gates — validates prod-like config
- **PROD:** double safety — Jenkins manual approval + ArgoCD manual sync
- **Kustomize overlays:** DRY — shared base, only diffs in overlays

### 3 ArgoCD Applications

| App | Namespace | Sync Policy | When Updated |
|-----|-----------|-------------|-------------|
| learneasyai-dev | project-dev | Auto-sync + selfHeal | Every commit |
| learneasyai-staging | project-staging | Auto-sync + selfHeal | After DEV gates pass |
| learneasyai-prod | project-prod | **Manual sync** | After manual approval |

**Why manual sync for prod?** Double safety — Jenkins approval gate + ArgoCD sync approval = two separate humans must agree.


---

## 9. Canary Deployment & Auto-Rollback

### What is Canary?

Instead of switching all traffic to the new version at once, route a small percentage first. If the new version is broken, only 5% of users are affected — not 100%.

### How It Works in This Project

```
New image deployed → 5% traffic → Prometheus check → PASS?
    → 20% → check → PASS?
    → 50% → check → PASS?
    → 80% → check → PASS?
    → 100% (full promotion)

At ANY step: FAIL → traffic goes back to 0% canary (auto-rollback)
```

### Argo Rollout (replaces Deployment in prod)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: learneasyai
spec:
  replicas: 3
  strategy:
    canary:
      canaryService: learneasyai-canary
      stableService: learneasyai-service
      trafficRouting:
        nginx:
          stableIngress: learneasyai-ingress
      steps:
        - setWeight: 5
        - pause: { duration: 1m }
        - analysis:
            templates: [{ templateName: canary-success-rate }]
        - setWeight: 20
        - pause: { duration: 2m }
        - analysis:
            templates: [{ templateName: canary-success-rate }]
        - setWeight: 50
        - pause: { duration: 2m }
        - analysis:
            templates: [{ templateName: canary-success-rate }]
        - setWeight: 80
        - pause: { duration: 2m }
        - analysis:
            templates: [{ templateName: canary-success-rate }]
```

### Analysis Metrics (Prometheus Queries)

| Metric | Query Logic | Threshold | On Fail |
|--------|-------------|-----------|---------|
| Success Rate | non-5xx / total requests | > 95% | Immediate rollback |
| P99 Latency | histogram_quantile(0.99, ...) | < 500ms | Immediate rollback |
| Error vs Stable | canary_error / stable_error | ≤ 2x | Rollback after 2 failures |

### Auto-Rollback Scenario (Real Timeline)

```
T+0m:   New image pushed. ArgoCD syncs. Canary pods created.
T+0m:   5% traffic routed to canary.
T+1m:   Pause complete. AnalysisRun queries Prometheus.
T+1.5m: Prometheus says: success rate = 90% (threshold: 95%)
T+2m:   AnalysisRun: FAILED. Argo Rollouts aborts.
T+2m:   Canary weight → 0%. All traffic back to stable.
T+7m:   Failed canary pods kept 5 min for debugging, then removed.

Result: 95% of users NEVER saw the bug. Total exposure: 2 minutes for 5% of users.
```

### Canary vs Rolling Update vs Blue-Green

| Strategy | Blast Radius | Rollback Speed | Complexity |
|----------|-------------|----------------|------------|
| Rolling Update | 100% eventually | Manual, slow | Low |
| Blue-Green | 100% instant | Fast (switch back) | Medium |
| **Canary** | **5% → gradual** | **Automatic, 2 min** | High |

---

## 10. Observability Stack

### Components

| Tool | Role |
|------|------|
| Prometheus | Scrapes metrics, stores time series, runs alert rules |
| Grafana | Dashboards — visualize canary vs stable in real-time |
| ServiceMonitor | Tells Prometheus what to scrape |
| PrometheusRule | Alert conditions (HighErrorRate, HighLatency) |
| AnalysisTemplate | Prometheus queries as canary promotion gates |

### How Observability Drives Deployments

```
Nginx Ingress → exposes metrics (request rate, errors, latency)
       ↓
Prometheus → scrapes every 15s → stores time series
       ↓
AnalysisTemplate → queries Prometheus at each canary step
       ↓
Results: PASS → promote to next weight
         FAIL → abort → rollback
       ↓
Grafana → shows the whole thing in real-time dashboards
```

### Alert Rules

```yaml
# Alert: >5% error rate for 2 minutes
- alert: HighErrorRate
  expr: |
    sum(rate(nginx_ingress_controller_requests{status=~"5.."}[5m]))
    / sum(rate(nginx_ingress_controller_requests[5m])) > 0.05
  for: 2m
  labels: { severity: critical }
  annotations:
    summary: "High error rate on LearnEasyAI production"

# Alert: P99 latency >1 second
- alert: HighLatency
  expr: |
    histogram_quantile(0.99, sum(rate(
      nginx_ingress_controller_request_duration_seconds_bucket[5m]
    )) by (le)) > 1
  for: 3m
  labels: { severity: warning }
```

### Grafana Dashboard Panels

- Traffic split (canary vs stable requests/sec)
- Error rate comparison (canary vs stable %)
- Latency P50/P99 comparison
- HTTP status code distribution (pie chart)
- Pod restart count
- Replica availability

### How Canary + Observability Works End-to-End

```
Jenkins Approval → Git Push (prod overlay) → ArgoCD Sync
                                                  │
                                                  ▼
                              Argo Rollouts creates canary pods
                                                  │
                                                  ▼
         ┌────────────────────────────────────────────────────────────┐
         │          CANARY PROGRESSION (automated)                     │
         │                                                            │
         │  5% traffic → Prometheus check → PASS? → 20% traffic      │
         │  20% traffic → Prometheus check → PASS? → 50% traffic     │
         │  50% traffic → Prometheus check → PASS? → 80% traffic     │
         │  80% traffic → Prometheus check → PASS? → 100% (done!)    │
         │                                                            │
         │  At ANY step: FAIL? → rollback to 0% → stable serves all  │
         └────────────────────────────────────────────────────────────┘
                                                  │
                              Grafana shows real-time:
                              • Traffic split (canary vs stable)
                              • Error rate comparison
                              • Latency P50/P99 comparison
                              • Pod health
```

### Prometheus Analysis Gates (3 Metrics)

| Metric | Threshold | Action on Fail |
|--------|-----------|---------------|
| Success rate | Must be > 95% | Immediate rollback |
| P99 latency | Must be < 500ms | Immediate rollback |
| Error rate vs stable | Must be ≤ 2x stable | Rollback after 2 failures |

### Alert Rules (Grafana/PagerDuty/Slack)

| Alert | Condition | Severity |
|-------|-----------|----------|
| HighErrorRate | >5% errors for 2 min | Critical |
| HighLatency | P99 >1s for 3 min | Warning |
| FrequentPodRestarts | >3 restarts in 15 min | Warning |
| CanaryRollbackOccurred | auto-rollback detected | Critical |

This puts the pipeline at **Level 5 (Platform) maturity**. The auto-rollback with observability gates is what top-tier companies like Netflix, Intuit, and Lyft use in production.

---

## 11. Pipeline Portability — Python vs Java vs Go vs Node.js

The pipeline structure stays ~80% the same across languages. Only the tool/command within each stage changes.

**What stays IDENTICAL (language-agnostic):**
- Secret Scanning (Trivy filesystem)
- Docker Build (multi-stage)
- Container Scan (Trivy image)
- Image Push + Sign (Cosign)
- GitOps (ArgoCD)
- DAST (OWASP ZAP)
- S3 Reports
- Kyverno admission

**What changes per language (only 4 stages):**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CI/CD PIPELINE STRUCTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ Checkout │───▶│ Secret   │───▶│  Unit    │───▶│   SCA    │             │
│  │   SCM    │    │ Scanning │    │  Tests   │    │          │             │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘             │
│                   SAME ✅         CHANGES ⚠️       CHANGES ⚠️              │
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │   SAST   │───▶│ Quality  │───▶│  Docker  │───▶│  Trivy   │             │
│  │          │    │  Gate    │    │  Build   │    │  Image   │             │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘             │
│   CHANGES ⚠️      SAME ✅         SAME ✅          SAME ✅                 │
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │  Push +  │───▶│    S3    │───▶│  GitOps  │───▶│   DAST   │             │
│  │  Cosign  │    │ Reports  │    │ (ArgoCD) │    │  (ZAP)   │             │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘             │
│   SAME ✅         SAME ✅          SAME ✅          SAME ✅                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Stage-wise differences per language:**

| Stage | Python | Java | Go | Node.js |
|-------|--------|------|-----|---------|
| Unit Test | `pytest --cov` | `mvn test` / `gradle test` | `go test ./... -cover` | `npm test` / `jest --coverage` |
| SCA | Snyk / pip-audit (`requirements.txt`) | Snyk / OWASP Dependency-Check (`pom.xml`) | Snyk / `govulncheck` (`go.sum`) | Snyk / `npm audit` (`package.json`) |
| SAST | SonarQube / Bandit | SonarQube / SpotBugs / Checkmarx | SonarQube / gosec / staticcheck | SonarQube / ESLint security / Semgrep |
| Dockerfile base | python:3.9-slim + gunicorn | eclipse-temurin + JRE only (no JDK) | golang:1.21 → scratch/distroless | node:20-slim + pm2 |

**Docker multi-stage difference:**

```
Python:                        Java:                         Go:
┌────────────────┐            ┌────────────────┐           ┌────────────────┐
│ Builder        │            │ Builder        │           │ Builder        │
│ pip install    │            │ mvn package    │           │ go build       │
│ (gcc, wheels)  │            │ (JDK + Maven)  │           │ (Go toolchain) │
└───────┬────────┘            └───────┬────────┘           └───────┬────────┘
        │ copy packages               │ copy .jar                  │ copy binary
        ▼                             ▼                            ▼
┌────────────────┐            ┌────────────────┐           ┌────────────────┐
│ Production     │            │ Production     │           │ Production     │
│ python-slim    │            │ JRE only       │           │ scratch /      │
│ ~150MB         │            │ ~200MB         │           │ distroless     │
└────────────────┘            └────────────────┘           │ ~10-20MB !!    │
                                                           └────────────────┘
```

**Bottom line:** Pipeline architecture is identical across languages. You swap 3-4 commands (test runner, SCA tool, SAST scanner, base image). Everything from Docker build onwards is completely language-agnostic. That's the beauty of containerization — once it's an image, the pipeline doesn't care what's inside.

---

## 12. Design Decisions

| # | Decision | Why (Not the Alternative) |
|---|----------|--------------------------|
| 1 | Multi-stage Dockerfile | 900MB→150MB. No build tools in prod = smaller attack surface |
| 2 | Git-SHA image tags | Immutable, traceable. `:latest` is mutable — can't trace what's running |
| 3 | Scan BEFORE push | Vulnerable images never reach registry. Old order pushed first, scanned after |
| 4 | Cosign + Kyverno | Only CI/CD-built images run. Prevents registry compromise, rogue pushes |
| 5 | ArgoCD over Ansible | Zero-downtime, drift detection, git audit. Ansible: SSH + downtime |
| 6 | ClusterIP + Ingress | TLS, domain routing, hidden nodes. NodePort: no TLS, ugly URL |
| 7 | 3 replicas + PDB | HA, zero-downtime deploys, safe maintenance. 1 replica = downtime |
| 8 | Multi-env promotion | Catch bugs in dev/staging first. Direct-to-prod = risky |
| 9 | Canary over Rolling | 95% users unaffected. Rolling: 100% affected before you notice |
| 10 | Prometheus rollback | 2 min auto-detection. Human response = 30+ minutes |
| 11 | Kustomize over Helm | Simpler for single app. Plain YAML patches, easy PR reviews |
| 12 | Separate GitOps repo | Separation of concerns. App devs can't accidentally modify infra |
| 13 | DAST as promotion gate | Catches runtime issues before staging/prod |
| 14 | Secret scan first | Fail fastest. Don't waste compute if credentials are leaked |
| 15 | Manual approval (prod) | Human-in-the-loop. Compliance + double safety with ArgoCD |

---

## 13. Interview Quick Reference

### One-Liner Summary

> Built an enterprise-grade DevSecOps pipeline with 18 stages, 6 security layers, multi-environment promotion (Dev→Staging→Prod), canary deployments via Argo Rollouts with Prometheus-driven auto-rollback, and GitOps deployment via ArgoCD. Every image in production is: tested, scanned, signed, verified, and canary-validated.

### Key Numbers

| Metric | Value |
|--------|-------|
| Pipeline stages | 18 |
| Security layers | 6 |
| Environments | 3 (Dev, Staging, Prod) |
| Docker image reduction | 900MB → 150MB |
| Canary steps | 5% → 20% → 50% → 80% → 100% |
| Rollback time | ~2 minutes (automated) |
| User impact on bad deploy | 5% (not 100%) |
| Prometheus metrics checked | 3 (success rate, latency, error comparison) |

### What Makes It Enterprise-Grade

1. **Security at every stage** — not just one scan at the end
2. **Fail fast** — secrets caught at stage 3, not stage 18
3. **Immutable artifacts** — same image through all environments
4. **Zero-trust supply chain** — unsigned images can't run
5. **Automated rollback** — machines faster than humans
6. **GitOps** — git is truth, everything auditable
7. **Multi-env gates** — bugs caught before reaching users

### Common Interview Questions (Quick Answers)

**Q: Walk me through your pipeline.**  
A: 18 stages in 3 phases — Build (secret scan → SCA → SAST → Docker → Trivy → sign), Deploy (dev → DAST → staging → approval → prod canary), and Validate (Prometheus analysis at each canary step, auto-rollback on failure).

**Q: What if a dev pushes an API key?**  
A: Three layers catch it — pre-commit hooks, GitHub Push Protection, and Trivy CI scan (hard gate). If it reaches Git history, rotate immediately + BFG Repo-Cleaner.

**Q: Why scan before push?**  
A: Old order: build → push → scan. Problem: vulnerable image is already in registry. New order: build → scan → push only if clean. Vulnerable images never leave the build agent.

**Q: How does canary rollback work?**  
A: 5% traffic to canary → Prometheus checks success rate (>95%), latency (<500ms), error rate (≤2x stable). If any metric fails → Argo Rollouts sets canary weight to 0% → all traffic back to stable. Takes ~2 minutes. 95% users never saw the bug.

**Q: Why ArgoCD over Jenkins kubectl?**  
A: Jenkins never touches the cluster — only updates Git. ArgoCD pulls from Git, applies with rolling update, detects drift (reverts manual changes), and rollback = git revert. Full audit trail in git log.

**Q: What would you improve next?**  
A: External Secrets Operator (no manual kubectl secrets), dedicated /health/ endpoint, SBOM generation for compliance, non-root container user, dynamic PR environments.

---

## 13. CI/CD Pipeline for VMs — Container vs VM Comparison

### Why This Section?

Project 1's pipeline is container/K8s-native. But many production environments still deploy to VMs (banking, telecom, legacy apps, regulated environments where containers aren't approved). Here's how the same security-first CI/CD philosophy applies to VM deployments.

### Architecture Comparison

**Container Pipeline (What We Built):**
```
Code → Build Docker Image → Scan Image → Sign Image → Push to Registry → 
GitOps Repo Update → ArgoCD Pulls → K8s Rolling Update → Canary (Argo Rollouts)
```

**VM Pipeline (Same Security, Different Delivery):**
```
Code → Build Artifact (JAR/WAR) → Scan Dependencies → SAST → Upload to Artifactory →
Bake AMI (Packer) → Scan AMI → Update Launch Template → ASG Instance Refresh → 
ALB Health Check → Rolling Replacement
```

### Side-by-Side Pipeline Stages

| Stage | Container/K8s (Project 1) | VM/ASG (Equivalent) |
|-------|--------------------------|---------------------|
| **1. Cleanup** | cleanWs() | cleanWs() |
| **2. Checkout** | Git clone | Git clone |
| **3. Secret Scan** | Trivy filesystem (secret mode) | Trivy filesystem (secret mode) — identical |
| **4. Unit Tests** | pytest --cov | mvn test / pytest (same) |
| **5. SCA** | Snyk (requirements.txt) | Snyk / OWASP Dependency-Check (pom.xml) |
| **6. SAST** | SonarQube + Quality Gate | SonarQube + Quality Gate — identical |
| **7. Build** | `docker build` (multi-stage) | `mvn clean package` → JAR/WAR OR `packer build` → AMI |
| **8. Artifact Scan** | Trivy image scan (before push) | Trivy filesystem on AMI OR Inspector scan |
| **9. Push Artifact** | Push to DockerHub/ECR | Upload JAR to Nexus/Artifactory OR register AMI |
| **10. Sign** | Cosign sign (image) | Code signing (JAR) or AMI tagging with SHA |
| **11. Deploy to Dev** | Update GitOps repo → ArgoCD syncs | Ansible playbook → deploy to dev VMs |
| **12. DAST** | OWASP ZAP against dev URL | OWASP ZAP against dev URL — identical |
| **13. Smoke Test** | curl health check | curl health check — identical |
| **14. Promote Staging** | Update staging overlay in Git | Ansible → deploy to staging fleet |
| **15. Smoke Test Staging** | curl health check | curl health check — identical |
| **16. Approval** | Manual approval (Jenkins input) | Manual approval — identical |
| **17. Deploy Prod** | Update prod overlay → ArgoCD | ASG instance refresh OR Ansible rolling |
| **18. Verify** | Prometheus canary analysis | ALB health + CloudWatch metrics |

### VM Deployment — Two Strategies

**Strategy A: AMI-Based (Immutable — Recommended)**

```
┌──────────────────────────────────────────────────────────┐
│  Jenkins Pipeline                                         │
│                                                          │
│  1. Build JAR (mvn clean package)                        │
│  2. Packer builds AMI:                                   │
│     - Base: Amazon Linux 2023                            │
│     - Install: Java 17, CloudWatch Agent                 │
│     - Copy: app.jar + systemd unit file                  │
│     - Harden: disable root SSH, remove unnecessary pkgs  │
│  3. Trivy scans AMI (filesystem mode)                    │
│  4. Register AMI with git-SHA tag                        │
│  5. Update Launch Template → new AMI ID                  │
│  6. Trigger ASG Instance Refresh:                        │
│     - min_healthy_percentage: 80%                        │
│     - One instance at a time replaced                    │
│     - New instance boots with new AMI                    │
│     - ALB health check passes → old instance terminated  │
│  7. Verify: all instances on new AMI                     │
└──────────────────────────────────────────────────────────┘
```

**Why immutable (AMI)?**
- What you tested = what you deploy (no config drift)
- Rollback = point Launch Template to previous AMI (instant)
- No SSH needed post-deploy (nothing to configure at runtime)
- Reproducible — same AMI on 3 instances or 300

**Strategy B: Ansible Push (Mutable — Legacy/Quick)**

```
┌──────────────────────────────────────────────────────────┐
│  Jenkins Pipeline                                         │
│                                                          │
│  1. Build JAR (mvn clean package)                        │
│  2. Upload JAR to Nexus/S3                               │
│  3. Ansible playbook (serial: 20%, max_fail: 10%):       │
│     a. Deregister from ALB (wait drain 60s)              │
│     b. Stop application service                          │
│     c. Download new JAR from Nexus/S3                    │
│     d. Start application service                         │
│     e. Health check (retries: 10, delay: 5s)             │
│     f. Re-register to ALB (wait healthy)                 │
│  4. Verify: all instances healthy in target group        │
└──────────────────────────────────────────────────────────┘
```

**When to use which?**

| Approach | AMI (Immutable) | Ansible (Mutable) |
|---|---|---|
| Best for | Cloud-native, ASG, production | On-prem, quick deploys, config changes |
| Deploy time | 5-10 min (AMI bake + refresh) | 2-5 min (just copy + restart) |
| Rollback | Change AMI ID (instant, tested) | Re-run with previous version |
| Drift risk | Zero (fresh VM every deploy) | Possible (VM state accumulates) |
| Debugging | Can't SSH (immutable = rebuild) | Can SSH and inspect |

### Security Comparison

| Security Layer | Container Pipeline | VM Pipeline |
|---|---|---|
| **Secret scanning** | Trivy filesystem | Trivy filesystem — same |
| **Dependency scan** | Snyk (requirements.txt) | Snyk / OWASP Dep-Check (pom.xml) |
| **SAST** | SonarQube | SonarQube — same |
| **Artifact scan** | Trivy image (CVEs in base image) | Trivy filesystem on AMI / Inspector |
| **Supply chain** | Cosign (image signature) | Code signing (JAR) + AMI tagging |
| **Admission control** | Kyverno (reject unsigned images) | AMI validation (only approved AMIs in Launch Template) |
| **Runtime** | Falco, Network Policies | CrowdStrike/OSSEC, Security Groups |
| **DAST** | OWASP ZAP | OWASP ZAP — same |

### Rollback Comparison

| Aspect | Container/K8s | VM/ASG |
|---|---|---|
| **How** | Git revert → ArgoCD syncs previous image | Update Launch Template → previous AMI → instance refresh |
| **Time** | ~30 seconds (pods replaced) | ~5 minutes (instances replaced) |
| **Blast radius** | Namespace-level (one app) | ASG-level (one service) |
| **Data safety** | Stateless (DB external) | Stateless (DB external) — same |
| **Automation** | Argo Rollouts auto-rollback on metrics | CloudWatch alarm → Lambda → revert Launch Template |

### Monitoring & Logging (VM vs Container)

| Aspect | Container (K8s) | VM (EC2/ASG) |
|---|---|---|
| **Metrics** | Prometheus + ServiceMonitor (auto-discovery) | CloudWatch Agent + custom metrics (install on each VM) |
| **Logs** | stdout → FluentBit DaemonSet → CloudWatch/Loki | CloudWatch Agent reads log files → CloudWatch Logs |
| **Dashboards** | Grafana (in-cluster) | CloudWatch Dashboards or Grafana (external) |
| **Alerting** | AlertManager → PagerDuty/Slack | CloudWatch Alarms → SNS → PagerDuty/Slack |
| **Tracing** | OpenTelemetry SDK → Tempo/Jaeger | X-Ray SDK → AWS X-Ray |
| **Health** | Liveness + readiness probes | ALB health check + custom /health endpoint |

### Jenkinsfile Comparison (Key Stages)

**Container — Deploy Stage:**
```groovy
stage("Deploy to PROD") {
    steps {
        script {
            // Update image tag in GitOps repo — ArgoCD handles the rest
            sh """
                cd dcp_devsecops-gitops
                sed -i 's|newTag:.*|newTag: ${IMAGE_TAG}|' overlays/prod/kustomization.yml
                git commit -am '[PROD] Deploy image ${IMAGE_TAG}'
                git push origin main
            """
        }
    }
}
```

**VM — Deploy Stage (AMI approach):**
```groovy
stage("Deploy to PROD") {
    steps {
        script {
            // Update Launch Template with new AMI
            sh """
                aws ec2 create-launch-template-version \
                    --launch-template-id ${LT_ID} \
                    --source-version \$Latest \
                    --launch-template-data '{"ImageId":"${NEW_AMI_ID}"}'

                aws autoscaling start-instance-refresh \
                    --auto-scaling-group-name prod-app-asg \
                    --preferences '{"MinHealthyPercentage":80,"InstanceWarmup":120}'
            """
        }
    }
}
```

**VM — Deploy Stage (Ansible approach):**
```groovy
stage("Deploy to PROD") {
    steps {
        script {
            sh """
                ansible-playbook -i inventory/prod deploy.yml \
                    -e "app_version=${IMAGE_TAG}" \
                    -e "artifact_url=s3://artifacts/app-${IMAGE_TAG}.jar" \
                    --forks=5
            """
            // Ansible handles: ALB drain → stop → deploy → start → health → re-register
            // serial: 20% + max_fail_percentage: 10%
        }
    }
}
```

### Interview Quick Answer

**Q: "Your pipeline is for K8s. How would you deploy to VMs?"**

A: Same security stages (scan, SAST, SCA, DAST) — those are artifact-agnostic. The difference is delivery. Instead of Docker image → ArgoCD → K8s, we'd either:
1. **Immutable (recommended):** Packer bakes AMI with app → Trivy scans AMI → update Launch Template → ASG instance refresh (80% healthy, rolling). Rollback = revert AMI ID.
2. **Ansible (legacy/on-prem):** Upload JAR to Nexus → Ansible deploys in 20% batches (ALB drain → deploy → health check → re-register). Rollback = re-run with previous version.

The security pipeline is identical — only the last-mile delivery changes.

---

---

## 14. CI vs Continuous Delivery vs Continuous Deployment

### The Confusion

These three terms sound similar but mean very different things. Many engineers use them interchangeably — interviewers notice.

### Simple Definition

| Term | What It Means | Ends At |
|------|---------------|---------|
| **CI (Continuous Integration)** | Every commit is automatically built and tested | ✅ "Code works" — artifact ready |
| **Continuous Delivery** | Every commit is automatically built, tested, AND ready to deploy — but needs **human approval** to go to prod | ✅ "Code is deployable" — button click away |
| **Continuous Deployment** | Every commit is automatically built, tested, AND deployed to production — **no human involved** | ✅ "Code is live" — fully automated |

### Visual Comparison

```
CONTINUOUS INTEGRATION (CI):
  Code → Build → Unit Test → Integration Test → ✅ Artifact Ready
                                                   (STOPS HERE)
                                                   Human decides when to deploy

CONTINUOUS DELIVERY:
  Code → Build → Test → Scan → Stage Deploy → ✅ Ready for Prod
                                                   (STOPS HERE)
                                                   Human clicks "Deploy to Prod"

CONTINUOUS DEPLOYMENT:
  Code → Build → Test → Scan → Stage → Prod Deploy → ✅ Live
                                                   (NO STOP)
                                                   Fully automatic, no human
```

### Real-World Example: Online Food Ordering App

**Scenario:** Developer fixes a bug in the checkout page.

**With CI only:**
1. Developer pushes code
2. Jenkins runs tests — all pass ✅
3. Docker image built and stored in registry
4. **DONE.** Operations team manually deploys next Thursday during maintenance window.
5. Bug fix reaches users: **5 days later**

**With Continuous Delivery:**
1. Developer pushes code
2. Jenkins runs tests, scans, builds image ✅
3. Auto-deployed to staging, smoke tests pass ✅
4. Slack message: "v2.3.1 ready for production. Approve?"
5. Tech lead clicks **"Deploy"** → goes to prod
6. Bug fix reaches users: **2 hours later** (waiting for approval)

**With Continuous Deployment:**
1. Developer pushes code
2. Jenkins runs tests, scans, builds image ✅
3. Auto-deployed to staging, smoke tests pass ✅
4. Auto-deployed to production (canary 5% → 20% → 100%) ✅
5. **No human involved.** Prometheus monitors — auto-rollback if errors spike.
6. Bug fix reaches users: **15 minutes later**

### Which Does Our Project Use?

**Our pipeline = Continuous Delivery (with option for Continuous Deployment)**

```
Code → Secret Scan → Tests → SAST → Build → Trivy → Sign → Push →
Deploy Dev (auto) → DAST → Smoke (auto) →
Deploy Staging (auto) → Smoke (auto) →
┌─────────────────────────────────┐
│  MANUAL APPROVAL ← This is     │  ← Continuous DELIVERY
│  what makes it "Delivery"       │     (human gate before prod)
│  not "Deployment"               │
└─────────────────────────────────┘
Deploy Prod (after approval) → Canary → Auto-rollback if metrics fail
```

**To convert to Continuous Deployment:** Remove the manual approval stage. Everything auto-promotes if gates pass. Many mature teams do this — but requires high confidence in:
- Test coverage (>90%)
- Canary + auto-rollback working perfectly
- Feature flags (hide incomplete features)
- Fast rollback (<1 min)

### When to Use Which

| Approach | Best For | Risk Tolerance | Example Companies |
|---|---|---|---|
| **CI only** | Regulated/legacy, release committees | Low (monthly releases OK) | Banks (mainframe), government |
| **Continuous Delivery** | Most companies, enterprise apps | Medium (deploy on demand) | Most startups, SaaS companies |
| **Continuous Deployment** | Mature DevOps, high test confidence | High (deploy every commit) | Netflix, Amazon, Facebook, Etsy |

### Key Interview Points

1. **CI is NOT deployment** — CI only builds and tests. Stops at "artifact ready."
2. **Delivery vs Deployment = human approval** — that's the ONLY difference.
3. **Continuous Deployment requires:** excellent test coverage, feature flags, auto-rollback, monitoring-driven decisions.
4. **Most companies claim CD but actually do Continuous Delivery** (manual approval before prod).
5. **Our project supports both** — remove the `input` stage in Jenkinsfile = Continuous Deployment.

### One-Liner for Interview

> "CI means every commit is built and tested. Continuous Delivery means it's also ready to deploy with one click. Continuous Deployment means it actually deploys automatically. The difference between Delivery and Deployment is one `input` stage in the pipeline — a human approval gate."

---

## 15. Multi-Language Pipeline Strategy

### The Problem

Real companies have 50+ microservices in different languages. You can't maintain 50 separate Jenkinsfiles. Need: **shared pipeline template** where language-specific stages are parameterized but security + deploy stages are identical.

### The Pattern: Language Changes the Build, Not the Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  SHARED STAGES (language-agnostic — same for ALL services)  │
│                                                             │
│  Checkout → Secret Scan → SAST → Quality Gate →            │
│  Docker Build → Trivy Scan → Sign → Push →                 │
│  Deploy Dev → DAST → Smoke → Promote → Deploy Prod         │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼──────────────────┐
        │                 │                  │
┌───────▼──────┐  ┌──────▼───────┐  ┌──────▼───────┐
│   PYTHON     │  │    JAVA      │  │   NODE.JS    │
│              │  │              │  │              │
│ pip install  │  │ mvn package  │  │ npm ci       │
│ pytest --cov │  │ mvn test     │  │ npm test     │
│ Snyk (pip)   │  │ JaCoCo       │  │ npm audit    │
│ coverage.xml │  │ OWASP DepChk │  │ jest --cov   │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Language-Specific Build Stages

| Stage | Python | Java (Maven) | Node.js | Go |
|-------|--------|-------------|---------|-----|
| **Install deps** | `pip install -r requirements.txt` | `mvn dependency:resolve` | `npm ci` | `go mod download` |
| **Unit tests** | `pytest --cov --cov-report=xml` | `mvn test` | `npm test -- --coverage` | `go test ./... -coverprofile=coverage.out` |
| **Coverage tool** | pytest-cov | JaCoCo (plugin in pom.xml) | Jest/Istanbul | go tool cover |
| **SCA scan** | `snyk test --file=requirements.txt` | `mvn org.owasp:dependency-check-maven:check` OR `snyk test --file=pom.xml` | `npm audit --audit-level=high` OR `snyk test` | `snyk test` OR `govulncheck ./...` |
| **SAST** | SonarQube (sonar-scanner) | SonarQube (`mvn sonar:sonar` — integrated) | SonarQube (sonar-scanner) | SonarQube + golangci-lint |
| **Build artifact** | app code (no compile needed) | `mvn clean package -DskipTests` → JAR/WAR | `npm run build` → dist/ | `go build -o app` → binary |
| **Dockerfile base** | python:3.9-slim | eclipse-temurin:17-jre | node:18-alpine | gcr.io/distroless/static |
| **Image size** | ~150MB | ~200MB | ~100MB | ~20MB (distroless) |

### Shared Library Approach (Jenkins)

```groovy
// vars/devSecOpsPipeline.groovy — Shared Library
def call(Map config) {
    pipeline {
        agent any
        stages {
            stage('Checkout')      { steps { checkout scm } }
            stage('Secret Scan')   { steps { sh "trivy fs . --scanners secret --exit-code 1" } }

            // === LANGUAGE-SPECIFIC (parameterized) ===
            stage('Install & Test') {
                steps {
                    script {
                        switch(config.language) {
                            case 'python':
                                sh "pip install -r requirements.txt"
                                sh "pytest --cov --cov-report=xml"
                                break
                            case 'java':
                                sh "mvn clean package"
                                sh "mvn test"
                                break
                            case 'node':
                                sh "npm ci"
                                sh "npm test -- --coverage"
                                break
                            case 'go':
                                sh "go test ./... -coverprofile=coverage.out"
                                sh "go build -o app"
                                break
                        }
                    }
                }
            }

            stage('SCA') {
                steps {
                    sh "snyk test --file=${config.depFile} --severity-threshold=high || true"
                }
            }

            // === SHARED (identical for all languages) ===
            stage('SAST')          { steps { /* SonarQube scan */ } }
            stage('Quality Gate')  { steps { waitForQualityGate() } }
            stage('Docker Build')  { steps { /* docker build */ } }
            stage('Trivy Scan')    { steps { sh "trivy image ${config.imageName}:${IMAGE_TAG} --exit-code 1" } }
            stage('Sign & Push')   { steps { /* cosign sign + push */ } }
            stage('Deploy')        { steps { /* GitOps update or ASG refresh */ } }
            stage('DAST')          { steps { /* OWASP ZAP */ } }
        }
    }
}
```

**Each service's Jenkinsfile becomes 5 lines:**
```groovy
// Service-specific Jenkinsfile
@Library('devsecops-pipeline') _

devSecOpsPipeline(
    language: 'java',
    depFile: 'pom.xml',
    imageName: 'siddharthgopalpatel/order-service'
)
```

### GitHub Actions Equivalent (Reusable Workflow)

```yaml
# .github/workflows/build.yml (called by each service)
name: DevSecOps Pipeline
on:
  workflow_call:
    inputs:
      language:
        required: true
        type: string
      dep_file:
        required: true
        type: string

jobs:
  pipeline:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # OIDC for AWS
    steps:
      - uses: actions/checkout@v4

      - name: Secret Scan
        run: trivy fs . --scanners secret --exit-code 1

      # Language-specific build
      - name: Build & Test (Python)
        if: inputs.language == 'python'
        run: |
          pip install -r requirements.txt
          pytest --cov --cov-report=xml

      - name: Build & Test (Java)
        if: inputs.language == 'java'
        run: |
          mvn clean package
          mvn test

      - name: Build & Test (Node)
        if: inputs.language == 'node'
        run: |
          npm ci
          npm test -- --coverage

      # Shared stages (identical regardless of language)
      - name: SCA
        run: snyk test --file=${{ inputs.dep_file }} --severity-threshold=high

      - name: SAST (SonarQube)
        uses: sonarqube-scan-action@v2

      - name: Docker Build
        run: docker build -t $IMAGE_NAME:${{ github.sha }} .

      - name: Trivy Scan
        run: trivy image $IMAGE_NAME:${{ github.sha }} --exit-code 1 --severity HIGH,CRITICAL

      - name: Configure AWS (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/github-deploy

      - name: Push to ECR
        run: docker push $IMAGE_NAME:${{ github.sha }}

      - name: Deploy (GitOps)
        run: |
          # Update image tag in GitOps repo
```

**Each service calls it:**
```yaml
# order-service/.github/workflows/ci.yml
name: CI
on: [push]
jobs:
  build:
    uses: org/pipeline-templates/.github/workflows/build.yml@v2
    with:
      language: java
      dep_file: pom.xml
```

### Interview Quick Answers

**Q: "How do you handle 50 microservices in different languages?"**

A: Shared pipeline template. Each service has a 5-line Jenkinsfile (or workflow_call) specifying language and dependency file. The template handles everything — build varies by language, but security scans, container build, signing, and deployment are 100% identical. Platform team owns the template, dev teams own their 5-line config.

**Q: "Jenkins or GitHub Actions?"**

A: Both work. Jenkins for: self-hosted, complex enterprise, existing investment. GitHub Actions for: cloud-first, OIDC native, marketplace actions, simpler YAML. I've used both — same pipeline concepts, different syntax. I'd choose based on what the team already uses.

**Q: "How do you handle a new language (e.g., Rust)?"**

A: Add one `case 'rust'` block to the shared template: `cargo build`, `cargo test`, `cargo audit`. Everything else (scan, sign, push, deploy) unchanged. Takes 30 minutes to support a new language.

---

<div align="center">

### Project Files Reference

| File | Purpose |
|------|---------|
| `Jenkinsfile` | 18-stage DevSecOps pipeline |
| `Dockerfile` | Multi-stage build (900MB→150MB) |
| `.dockerignore` | Excludes .git, .env, tests from image |
| `k8s.yml` | Reference K8s manifests |
| `kyverno-policy.yml` | Reject unsigned images |
| `argocd-application.yml` | Legacy single-env ArgoCD |
| `gitops/` | Multi-env Kustomize + ArgoCD + Observability |

---

**Built by Siddharth Patel** | DevOps & Cloud Engineer  
GitHub: [siddharthpatel1993](https://github.com/siddharthpatel1993)

</div>
