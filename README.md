# 🔒 DevSecOps CI/CD Pipeline — Enterprise Production Grade

> End-to-end DevSecOps pipeline for a Django AI Learning Platform with security integrated at every stage — from code commit to canary production deployment on Kubernetes with automated observability-driven rollbacks.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Pipeline Stages (18 Stages)](#pipeline-stages-18-stages)
- [Security Layers (Defence in Depth)](#security-layers-defence-in-depth)
- [Multi-Environment Promotion](#multi-environment-promotion)
- [Canary Deployment with Auto-Rollback](#canary-deployment-with-auto-rollback)
- [Observability Stack](#observability-stack)
- [Kubernetes Production Setup](#kubernetes-production-setup)
- [GitOps with ArgoCD](#gitops-with-argocd)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Key Design Decisions](#key-design-decisions)
- [Technologies Used](#technologies-used)
- [Future Improvements](#future-improvements)

---

## Overview

This project demonstrates an **enterprise-grade DevSecOps pipeline** with:

- ✅ **Secret Scanning** — catch leaked API keys/tokens before they reach main branch
- ✅ **SCA (Snyk)** — scan dependencies for known vulnerabilities + license compliance
- ✅ **SAST (SonarQube)** — static code analysis for bugs, vulnerabilities, code smells
- ✅ **Container Scanning (Trivy)** — CVE scan BEFORE image reaches registry
- ✅ **Image Signing (Cosign)** — cryptographic supply chain integrity
- ✅ **Admission Control (Kyverno)** — only signed images run in cluster
- ✅ **DAST (OWASP ZAP)** — runtime vulnerability testing against deployed app
- ✅ **Multi-Environment Promotion** — Dev → Staging → Prod with automated gates
- ✅ **Canary Deployments (Argo Rollouts)** — 5% → 20% → 50% → 80% → 100% traffic shift
- ✅ **Observability-Driven Rollbacks** — Prometheus analysis auto-reverts on error spike
- ✅ **Grafana Dashboards** — real-time canary vs stable comparison
- ✅ **GitOps (ArgoCD)** — drift detection, self-heal, git-based rollback

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CI/CD + SECURITY PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Developer → Git Push → Jenkins (18 Stages)                                     │
│                              │                                                  │
│                              ├── Secret Scanning (Trivy — leaked credentials)   │
│                              ├── Unit Tests (pytest + coverage)                  │
│                              ├── SCA (Snyk — dependency vulnerabilities)         │
│                              ├── SAST (SonarQube + Quality Gate)                 │
│                              ├── Docker Build (multi-stage, 900MB → 150MB)       │
│                              ├── Container Scan (Trivy — gate on HIGH/CRIT)      │
│                              ├── Push + Sign (Cosign — supply chain proof)       │
│                              ├── S3 Reports (audit trail)                        │
│                              ├── Deploy to DEV (auto)                            │
│                              ├── DAST + Smoke Tests (DEV gate)                   │
│                              ├── Promote to STAGING (auto after gates)           │
│                              ├── Smoke Tests (STAGING gate)                      │
│                              ├── Manual Approval (authorized team)               │
│                              └── Deploy to PRODUCTION (canary rollout)           │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                    PRODUCTION CANARY DEPLOYMENT (Argo Rollouts)                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  5% traffic → Prometheus analysis → PASS → 20% → PASS → 50% → 80% → 100%     │
│                                      FAIL → AUTOMATIC ROLLBACK (0% canary)      │
│                                                                                 │
│  Metrics checked at each step:                                                  │
│    • Success rate > 95% (HTTP non-5xx)                                          │
│    • P99 Latency < 500ms                                                        │
│    • Error rate ≤ 2x stable version                                             │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                         OBSERVABILITY (Prometheus + Grafana)                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Grafana Dashboard: traffic split, error comparison, latency P50/P99            │
│  Alert Rules: HighErrorRate, HighLatency, PodRestarts, CanaryRollback           │
│  ServiceMonitor: auto-discovery of app + ingress metrics                        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Stages (18 Stages)

| # | Stage | Tool | Purpose | Gate |
|---|-------|------|---------|------|
| 1 | Cleanup Workspace | Jenkins | Fresh build environment | — |
| 2 | Checkout | Git | Clone source code | — |
| 3 | **Secret Scanning** | Trivy | Detect leaked API keys/passwords | **Fail pipeline** |
| 4 | Unit Tests | pytest | Code correctness + coverage | Fail on test failure |
| 5 | **SCA** | Snyk | Dependency vulnerabilities + license | Threshold: HIGH |
| 6 | SAST Analysis | SonarQube | Bugs, vulnerabilities, code smells | Quality Gate |
| 7 | Quality Gate | SonarQube | Threshold evaluation | Configurable block |
| 8 | Build Image | Docker | Multi-stage build (900MB → 150MB) | — |
| 9 | Container Scan | Trivy | CVE scan for HIGH/CRITICAL | **Fail pipeline** |
| 10 | Push Image | DockerHub | Push only clean images (Git-SHA tag) | — |
| 11 | Sign Image | Cosign | Cryptographic signature (supply chain) | — |
| 12 | S3 Reports | AWS S3 | Audit trail for compliance | — |
| 13 | **Deploy to DEV** | ArgoCD | Automatic deployment | — |
| 14 | **DAST (DEV)** | OWASP ZAP | Runtime vulnerability scan | Report to S3 |
| 15 | **Smoke Test (DEV)** | curl | Functional validation | **Fail pipeline** |
| 16 | **Promote to STAGING** | ArgoCD | Deploy validated build | — |
| 17 | **Smoke Test (STAGING)** | curl | Pre-prod validation | **Fail pipeline** |
| 18 | **Deploy to PROD** | Argo Rollouts | Canary with manual approval | **Manual gate** |

---

## Security Layers (Defence in Depth)

```
┌─────────────────────────────────────────────────────────────────┐
│                    6 SECURITY LAYERS                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: SECRETS                                                │
│  ├── Pre-commit hooks (detect-secrets — developer machine)       │
│  ├── GitHub Push Protection (server-side block)                  │
│  └── Trivy secret scan in CI (hard gate — pipeline fails)        │
│                                                                  │
│  Layer 2: DEPENDENCIES (SCA)                                     │
│  ├── Snyk scan (requirements.txt + transitive deps)              │
│  └── License compliance check                                    │
│                                                                  │
│  Layer 3: CODE (SAST)                                            │
│  ├── SonarQube (SQL injection, XSS, hardcoded creds)             │
│  ├── pytest coverage (untested code paths)                       │
│  └── Quality Gate (threshold enforcement)                        │
│                                                                  │
│  Layer 4: CONTAINER                                              │
│  ├── Trivy image scan (CVEs in OS packages + libraries)          │
│  ├── Multi-stage Dockerfile (no build tools in prod)             │
│  └── .dockerignore (no secrets/.git in image)                    │
│                                                                  │
│  Layer 5: SUPPLY CHAIN                                           │
│  ├── Cosign image signing (proof of CI/CD origin)                │
│  ├── Git-SHA tags (immutable, traceable)                         │
│  └── Kyverno policy (reject unsigned at admission)               │
│                                                                  │
│  Layer 6: RUNTIME                                                │
│  ├── OWASP ZAP DAST (XSS, CSRF, missing headers)                │
│  ├── Canary analysis (auto-rollback on error spike)              │
│  ├── K8s probes (readiness + liveness)                           │
│  ├── Resource limits (prevent noisy neighbor)                    │
│  └── Prometheus alerts (HighErrorRate, HighLatency)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Multi-Environment Promotion

```
     DEV (auto)                  STAGING (auto)               PROD (manual + canary)
┌────────────────┐          ┌────────────────┐          ┌────────────────────────┐
│ 1 replica      │  GATE 1  │ 2 replicas     │  GATE 2  │ 3 replicas             │
│ Low resources  │─────────▶│ Prod-like      │─────────▶│ Full resources         │
│ No TLS        │          │ TLS (staging)  │          │ TLS (production)       │
│ Auto-deploy   │          │ Auto-promote   │          │ Canary rollout         │
└────────────────┘          └────────────────┘          └────────────────────────┘
                   │                           │
          ┌────────┴────────┐         ┌────────┴─────────────┐
          │ • DAST pass     │         │ • Manual approval     │
          │ • Smoke test OK │         │ • Authorized team     │
          │ • No P1 bugs    │         │ • Canary 5%→20%→100% │
          └─────────────────┘         └──────────────────────┘

Same image promoted through all environments — built ONCE, scanned ONCE, signed ONCE.
```

**Kustomize Structure:**
```
gitops/
├── base/           (shared: Deployment, Service, PDB)
└── overlays/
    ├── dev/        (1 replica, 50m CPU, no Ingress)
    ├── staging/    (2 replicas, 100m CPU, staging TLS)
    └── prod/       (3 replicas, 200m CPU, prod TLS, Argo Rollout)
```

---

## Canary Deployment with Auto-Rollback

Production uses **Argo Rollouts** instead of standard Kubernetes Deployment:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    CANARY PROGRESSION                                  │
│                                                                      │
│  5% ──▶ Prometheus ──▶ PASS ──▶ 20% ──▶ Prometheus ──▶ PASS ──▶    │
│  50% ──▶ Prometheus ──▶ PASS ──▶ 80% ──▶ Prometheus ──▶ PASS ──▶   │
│  100% (full promotion — canary becomes new stable)                    │
│                                                                      │
│  At ANY step: FAIL ──▶ traffic routes back to stable (auto-rollback)│
│  95% of users NEVER see the bug. Rollback within 2 minutes.         │
└──────────────────────────────────────────────────────────────────────┘
```

**Analysis Metrics (checked at each step):**

| Metric | Threshold | On Failure |
|--------|-----------|------------|
| HTTP Success Rate | > 95% | Immediate rollback |
| P99 Latency | < 500ms | Immediate rollback |
| Error Rate vs Stable | ≤ 2x | Rollback after 2 failures |

---

## Observability Stack

| Component | Purpose |
|-----------|---------|
| **Prometheus** | Scrapes metrics (error rate, latency, request count) |
| **Grafana** | Dashboards — canary vs stable comparison |
| **ServiceMonitor** | Auto-discovers app + ingress metrics |
| **PrometheusRule** | Alert rules (HighErrorRate, HighLatency, PodRestarts) |
| **AnalysisTemplate** | Prometheus queries as canary promotion gates |

**Grafana Dashboard Panels:**
- Traffic split (canary vs stable req/s)
- Error rate comparison (canary vs stable %)
- Latency P50/P99 comparison
- HTTP status code distribution
- Pod restart count
- Replica availability

---

## Kubernetes Production Setup

| Resource | Configuration | Why |
|----------|--------------|-----|
| **Argo Rollout** | 3 replicas, canary strategy | Gradual traffic shift with analysis |
| Strategy | 5% → 20% → 50% → 80% → 100% | Minimize blast radius |
| Readiness Probe | httpGet /admin/ every 5s | Stop traffic to unhealthy pods |
| Liveness Probe | httpGet /admin/ every 10s | Restart deadlocked pods |
| Resources | requests + limits (CPU/memory) | Prevent noisy neighbor |
| Service | ClusterIP (stable) + ClusterIP (canary) | Traffic routing |
| Ingress | Nginx + TLS via cert-manager | HTTPS, canary annotations |
| PDB | minAvailable: 2 | Safe node maintenance |
| Kyverno | Reject unsigned images | Supply chain security |

---

## GitOps with ArgoCD

```
                           ┌─────────────────────┐
                           │   GitOps Repo        │
                           │   (Kustomize)        │
                           └──────────┬──────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │ ArgoCD App: DEV │    │ ArgoCD App: STG │    │ ArgoCD App: PROD│
    │ auto-sync       │    │ auto-sync       │    │ manual sync     │
    │ selfHeal: true  │    │ selfHeal: true  │    │ (extra safety)  │
    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Benefits:**
- 🔐 Jenkins never touches the cluster (no SSH/kubectl needed)
- 📝 Git history = deployment audit trail
- 🔄 Drift detection — manual `kubectl` changes auto-reverted
- ⏪ Rollback = `git revert` per environment (isolated)
- 🌐 Multi-cluster ready (same repo, multiple ArgoCD instances)
- 🎯 Prod = manual sync (double safety: Jenkins approval + ArgoCD approval)

---

## Project Structure

```
.
├── Jenkinsfile                     # 18-stage DevSecOps pipeline
├── Dockerfile                      # Multi-stage (builder → slim production)
├── .dockerignore                   # Excludes .git, .env, tests from image
├── k8s.yml                         # Reference K8s manifests (single-env)
├── kyverno-policy.yml              # Admission policy (reject unsigned images)
├── argocd-application.yml          # Legacy single-env ArgoCD config
├── requirements.txt                # Python dependencies
├── manage.py                       # Django management
├── LearnEasyAI/                    # Django project settings
├── learn/                          # Django app (views, urls, tests)
├── templates/                      # HTML templates
├── config/                         # Gunicorn config
│
└── gitops/                         # Multi-environment GitOps structure
    ├── argocd-applications.yml     # 3 ArgoCD apps (dev/staging/prod)
    ├── base/                       # Shared K8s resources (Kustomize)
    │   ├── deployment.yml
    │   ├── service.yml
    │   ├── pdb.yml
    │   └── kustomization.yml
    ├── overlays/
    │   ├── dev/                    # 1 replica, low resources, auto-deploy
    │   │   └── kustomization.yml
    │   ├── staging/                # 2 replicas, TLS, auto after gates
    │   │   ├── kustomization.yml
    │   │   └── ingress.yml
    │   └── prod/                   # 3 replicas, canary, manual approval
    │       ├── kustomization.yml
    │       ├── rollout.yml         # Argo Rollout (canary strategy)
    │       ├── analysis-template.yml # Prometheus analysis gates
    │       └── ingress.yml
    └── observability/
        ├── prometheus-servicemonitor.yml  # ServiceMonitor + Alert Rules
        ├── grafana-dashboard.yml          # Canary monitoring dashboard
        └── README-observability.md        # Full observability docs
```

---

## Prerequisites

| Tool | Purpose | Installation |
|------|---------|-------------|
| Jenkins | CI/CD orchestrator | Docker Compose or Helm on K8s |
| SonarQube | SAST + code quality | `docker run sonarqube:lts` |
| Trivy | Secret + container scanner | [Install guide](https://aquasecurity.github.io/trivy/) |
| Snyk | SCA — dependency scanning | `npm install -g snyk` |
| Cosign | Image signing | `brew install cosign` |
| ArgoCD | GitOps controller | `helm install argocd argo/argo-cd` |
| Argo Rollouts | Canary deployments | `helm install argo-rollouts argo/argo-rollouts` |
| Kyverno | Admission policy engine | `helm install kyverno kyverno/kyverno` |
| Prometheus | Metrics + alerting | `helm install prometheus prometheus-community/kube-prometheus-stack` |
| Grafana | Dashboards (included with kube-prometheus-stack) | Auto-installed |
| cert-manager | TLS certificate automation | `helm install cert-manager jetstack/cert-manager` |
| nginx-ingress | Ingress controller | `helm install ingress-nginx ingress-nginx/ingress-nginx` |

---

## Quick Start

```bash
# 1. Generate Cosign keypair (one-time)
cosign generate-key-pair
# → cosign.key (store in Jenkins credentials)
# → cosign.pub (use in Kyverno policy)

# 2. Install infrastructure (Helm)
helm install argocd argo/argo-cd -n argocd --create-namespace
helm install argo-rollouts argo/argo-rollouts -n argo-rollouts --create-namespace
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
helm install kyverno kyverno/kyverno -n kyverno-system --create-namespace

# 3. Apply policies and GitOps config
kubectl apply -f kyverno-policy.yml
kubectl apply -f gitops/argocd-applications.yml
kubectl apply -f gitops/observability/

# 4. Run Jenkins pipeline
# Pipeline handles: secrets → SCA → SAST → build → scan → sign → deploy (dev → staging → prod)

# 5. Monitor canary deployment
kubectl argo rollouts get rollout learneasyai -n project-prod --watch
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Multi-stage Dockerfile | 900MB → 150MB, no build tools in production |
| Git-SHA image tags | Immutable, traceable — never use `:latest` |
| Secret scan first | Fail fast — catch credentials before wasting build time |
| SCA before Docker build | Don't waste compute building an image with vuln deps |
| Scan BEFORE push | Vulnerable images never reach registry |
| Cosign + Kyverno | Only CI/CD-built images run in cluster |
| Multi-env promotion | Same image through dev→staging→prod — "what you test = what you deploy" |
| Canary over Rolling Update | 95% users unaffected during bad deploy vs 100% affected |
| Prometheus-driven rollback | Machine-speed detection — rollback in 2 min, not 30 min (human) |
| ArgoCD manual sync (prod) | Double safety — Jenkins approval + ArgoCD approval |
| Kustomize overlays | DRY — shared base, only diffs per environment |
| DAST as promotion gate | Catches runtime issues SAST can't see — before staging/prod |

---

## Technologies Used

| Category | Tools |
|----------|-------|
| **CI/CD** | Jenkins, ArgoCD, Argo Rollouts |
| **Security** | Trivy, Snyk, SonarQube, Cosign, Kyverno, OWASP ZAP |
| **Container** | Docker (multi-stage), DockerHub |
| **Orchestration** | Kubernetes, Helm, Kustomize |
| **Observability** | Prometheus, Grafana, ServiceMonitor, PrometheusRule |
| **GitOps** | ArgoCD (multi-env), Git, Kustomize overlays |
| **Cloud** | AWS S3 (reports), cert-manager (TLS) |
| **Application** | Python, Django, Gunicorn, OpenAI API, YouTube Transcript API |

---

## Future Improvements

- [ ] Non-root user in Dockerfile (commented out, needs permission fix)
- [ ] Dedicated `/health/` endpoint (currently using `/admin/` for probes)
- [ ] External Secrets Operator + AWS Secrets Manager (no manual kubectl secrets)
- [ ] SBOM generation (Syft/Trivy) for SOC2/FedRAMP compliance
- [ ] Jenkins on K8s with Helm (dynamic pod agents)
- [ ] DefectDojo integration (centralized vulnerability management)
- [ ] Dynamic PR environments (ephemeral namespace per PR)
- [ ] Chaos engineering (LitmusChaos — validate resilience)
- [ ] django-prometheus for application-level metrics

---

## Pipeline Maturity Level

```
Level 1: Basic          │ Build → Push → Deploy
Level 2: Standard       │ + Tests + Basic scanning
Level 3: Production     │ + Security gates + GitOps + Signing
Level 4: Enterprise     │ + Multi-env promotion + Automated gates
Level 5: Platform  ◄────│ + Canary + Observability-driven rollback ← YOU ARE HERE
```

---

## Author

**Siddharth Patel** — DevOps & Cloud Engineer

GitHub: [siddharthpatel1993](https://github.com/siddharthpatel1993)

---

## License

MIT
