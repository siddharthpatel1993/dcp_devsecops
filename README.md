# 🔒 DevSecOps CI/CD Pipeline — Production Ready

> End-to-end DevSecOps pipeline for a Django AI application with security integrated at every stage — from code commit to production deployment on Kubernetes.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Pipeline Stages](#pipeline-stages)
- [Security Layers](#security-layers)
- [Kubernetes Deployment](#kubernetes-deployment)
- [GitOps with ArgoCD](#gitops-with-argocd)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Key Design Decisions](#key-design-decisions)
- [Technologies Used](#technologies-used)

---

## Overview

This project demonstrates a **production-grade DevSecOps pipeline** that:

- ✅ Scans code for vulnerabilities (SAST)
- ✅ Scans container images for CVEs before pushing to registry
- ✅ Signs images cryptographically (supply chain security)
- ✅ Deploys via GitOps with zero-downtime rolling updates
- ✅ Tests the running application for runtime vulnerabilities (DAST)
- ✅ Stores audit reports in S3 for compliance
- ✅ Enforces admission policies (only signed images run in cluster)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CI/CD PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Developer → Git Push → Jenkins Pipeline                                    │
│                              │                                              │
│                              ├── Unit Tests (pytest + coverage)              │
│                              ├── SAST (SonarQube + Quality Gate)             │
│                              ├── Docker Build (multi-stage, slim)            │
│                              ├── Container Scan (Trivy — gate on HIGH/CRIT)  │
│                              ├── Push to Registry (only if scan passes)      │
│                              ├── Image Sign (Cosign — tamper-proof seal)     │
│                              ├── Update GitOps Repo (image tag in Git)       │
│                              └── DAST (OWASP ZAP — runtime scan)            │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                              DEPLOYMENT (GitOps)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ArgoCD (in-cluster) → Watches Git Repo → Detects Change                   │
│         │                                                                   │
│         ├── Compares: Git (desired) vs Cluster (actual)                     │
│         ├── Applies rolling update (zero-downtime)                          │
│         ├── Kyverno verifies image signature at admission                   │
│         └── Pod runs only if: tested + scanned + signed + verified          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Stages

| # | Stage | Tool | Purpose | Gate |
|---|-------|------|---------|------|
| 1 | Cleanup Workspace | Jenkins | Fresh build environment | — |
| 2 | Checkout | Git | Clone source code | — |
| 3 | Unit Tests | pytest | Code correctness + coverage | Fail on test failure |
| 4 | SAST Analysis | SonarQube | Bugs, vulnerabilities, code smells | Quality Gate |
| 5 | Quality Gate | SonarQube | Threshold evaluation | Configurable block |
| 6 | Build Image | Docker | Multi-stage build (slim production image) | — |
| 7 | Container Scan | Trivy | CVE scan for HIGH/CRITICAL | **Fail pipeline** |
| 8 | Push Image | DockerHub | Push only clean images | — |
| 9 | Sign Image | Cosign | Cryptographic signature (supply chain) | — |
| 10 | S3 Report | AWS S3 | Audit trail for compliance | — |
| 11 | GitOps Deploy | ArgoCD | Update image tag in Git → auto-sync | — |
| 12 | DAST Scan | OWASP ZAP | Runtime vulnerability scan | Report to S3 |

---

## Security Layers

```
┌─────────────────────────────────────────────────────┐
│                  DEFENCE IN DEPTH                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Layer 1: CODE                                      │
│  ├── SonarQube SAST (SQL injection, hardcoded creds)│
│  ├── pytest coverage (untested code paths)          │
│  └── Quality Gate (threshold enforcement)           │
│                                                     │
│  Layer 2: CONTAINER                                 │
│  ├── Trivy scan (CVEs in OS packages + libraries)   │
│  ├── Multi-stage Dockerfile (no build tools in prod)│
│  └── .dockerignore (no secrets/.git in image)       │
│                                                     │
│  Layer 3: SUPPLY CHAIN                              │
│  ├── Cosign image signing (proof of CI/CD origin)   │
│  ├── Git-SHA tags (immutable, traceable)            │
│  └── Kyverno policy (reject unsigned at admission)  │
│                                                     │
│  Layer 4: RUNTIME                                   │
│  ├── OWASP ZAP DAST (XSS, CSRF, missing headers)   │
│  ├── K8s probes (readiness + liveness)              │
│  └── Resource limits (prevent noisy neighbor)       │
│                                                     │
│  Layer 5: AUDIT                                     │
│  ├── Trivy HTML reports in S3                       │
│  ├── ZAP scan reports in S3                         │
│  └── Git history = deployment audit trail           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Kubernetes Deployment

Production-ready K8s manifests with:

| Resource | Configuration | Why |
|----------|--------------|-----|
| Deployment | 3 replicas, rolling update | HA + zero-downtime deploys |
| Strategy | maxSurge: 1, maxUnavailable: 0 | New pod ready before old killed |
| Readiness Probe | httpGet /admin/ every 5s | Stop traffic to unhealthy pods |
| Liveness Probe | httpGet /admin/ every 10s | Restart deadlocked pods |
| Resources | requests + limits (CPU/memory) | Prevent noisy neighbor |
| Service | ClusterIP (internal only) | Ingress handles external |
| Ingress | Nginx + TLS via cert-manager | HTTPS, domain routing |
| PDB | minAvailable: 2 | Safe node maintenance |
| ClusterIssuer | Let's Encrypt (auto-renew) | Free HTTPS certificates |

---

## GitOps with ArgoCD

```
Traditional (push):   Jenkins → SSH → kubectl apply    (fragile, no audit)
GitOps (pull):        Jenkins → Git push → ArgoCD sync (secure, auditable)
```

**Benefits:**
- 🔐 Jenkins never touches the cluster (no SSH/kubectl needed)
- 📝 Git history = deployment audit trail
- 🔄 Drift detection — manual `kubectl` changes auto-reverted
- ⏪ Rollback = `git revert` (instant, familiar)
- 🌐 Multi-cluster ready (same repo, multiple ArgoCD instances)

---

## Project Structure

```
.
├── Jenkinsfile                 # 12-stage DevSecOps pipeline
├── Dockerfile                  # Multi-stage (builder → slim production)
├── .dockerignore               # Excludes .git, .env, tests from image
├── k8s.yml                     # K8s manifests (Deployment, Service, Ingress, PDB)
├── kyverno-policy.yml          # Admission policy (reject unsigned images)
├── argocd-application.yml      # GitOps config (auto-sync, drift detection)
├── test.yml                    # [DEPRECATED] Old Ansible deployment
├── requirements.txt            # Python dependencies
├── manage.py                   # Django management
├── LearnEasyAI/                # Django project settings
├── learn/                      # Django app (views, urls, tests)
├── templates/                  # HTML templates
└── config/                     # Gunicorn config
```

---

## Prerequisites

| Tool | Purpose | Installation |
|------|---------|-------------|
| Jenkins | CI/CD orchestrator | Docker Compose or Helm on K8s |
| SonarQube | SAST + code quality | `docker run sonarqube:lts` |
| Trivy | Container vulnerability scanner | [Install guide](https://aquasecurity.github.io/trivy/) |
| Cosign | Image signing | `brew install cosign` or binary |
| ArgoCD | GitOps controller | `helm install argocd argo/argo-cd` |
| Kyverno | Admission policy engine | `helm install kyverno kyverno/kyverno` |
| cert-manager | TLS certificate automation | `helm install cert-manager jetstack/cert-manager` |
| nginx-ingress | Ingress controller | `helm install ingress-nginx ingress-nginx/ingress-nginx` |

---

## Quick Start

```bash
# 1. Generate Cosign keypair (one-time)
cosign generate-key-pair
# → cosign.key (store in Jenkins credentials)
# → cosign.pub (use in Kyverno policy)

# 2. Install ArgoCD
helm install argocd argo/argo-cd -n argocd --create-namespace

# 3. Apply Kyverno policy
kubectl apply -f kyverno-policy.yml

# 4. Apply ArgoCD Application
kubectl apply -f argocd-application.yml

# 5. Run Jenkins pipeline
# Pipeline handles: test → scan → build → sign → push → deploy
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Multi-stage Dockerfile | 900MB → 150MB, no build tools in production |
| Git-SHA image tags | Immutable, traceable — never use `:latest` |
| Scan BEFORE push | Vulnerable images never reach registry |
| Cosign + Kyverno | Only CI/CD-built images run in cluster |
| ArgoCD over Ansible | Zero-downtime, drift detection, git-based rollback |
| ClusterIP + Ingress | Single LB, HTTPS, path routing — not NodePort |
| 3 replicas + PDB | Survives failures, safe maintenance |
| DAST after deploy | Catches runtime issues SAST can't see |

---

## Technologies Used

| Category | Tools |
|----------|-------|
| **CI/CD** | Jenkins, ArgoCD |
| **Security** | SonarQube, Trivy, Cosign, Kyverno, OWASP ZAP |
| **Container** | Docker (multi-stage), DockerHub |
| **Orchestration** | Kubernetes, Helm |
| **IaC/GitOps** | ArgoCD, Git |
| **Cloud** | AWS S3 (reports), cert-manager (TLS) |
| **Monitoring** | Readiness/Liveness probes, PDB |
| **Application** | Python, Django, Gunicorn, OpenAI API |

---

## Author

**Siddharth Patel** — DevOps & Cloud Engineer (12 YOE)

---

## License

MIT
