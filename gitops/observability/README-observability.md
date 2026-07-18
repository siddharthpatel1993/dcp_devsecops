# =============================================================================
# OBSERVABILITY & CANARY DEPLOYMENT — Architecture Documentation
# =============================================================================
#
# This document explains how Canary deployments with Argo Rollouts and
# Prometheus/Grafana observability work together as automated deployment gates.
#
# =============================================================================
# ARCHITECTURE OVERVIEW
# =============================================================================
#
#   ┌─────────────────────────────────────────────────────────────────────┐
#   │                    CANARY DEPLOYMENT FLOW                            │
#   │                                                                     │
#   │   Jenkins pushes new image tag to GitOps repo (prod overlay)        │
#   │                          │                                          │
#   │                          ▼                                          │
#   │   ArgoCD detects change → syncs Argo Rollout resource               │
#   │                          │                                          │
#   │                          ▼                                          │
#   │   Argo Rollouts creates canary ReplicaSet (new version)             │
#   │                          │                                          │
#   │                          ▼                                          │
#   │   ┌──── Traffic Routing (Nginx Ingress Canary Annotations) ────┐   │
#   │   │                                                             │   │
#   │   │   Step 1: 5% → canary  │  95% → stable                    │   │
#   │   │   Step 2: 20% → canary │  80% → stable                    │   │
#   │   │   Step 3: 50% → canary │  50% → stable                    │   │
#   │   │   Step 4: 80% → canary │  20% → stable                    │   │
#   │   │   Step 5: 100% → canary (new stable)                       │   │
#   │   │                                                             │   │
#   │   └─────────────────────────────────────────────────────────────┘   │
#   │                          │                                          │
#   │                  Between each step:                                  │
#   │                          │                                          │
#   │                          ▼                                          │
#   │   ┌──── Prometheus Analysis (AnalysisTemplate) ─────────────────┐  │
#   │   │                                                              │  │
#   │   │   Metric 1: Success Rate > 95%?          ✅ PASS / ❌ FAIL  │  │
#   │   │   Metric 2: P99 Latency < 500ms?         ✅ PASS / ❌ FAIL  │  │
#   │   │   Metric 3: Error rate ≤ 2x stable?      ✅ PASS / ❌ FAIL  │  │
#   │   │                                                              │  │
#   │   │   ALL PASS → promote to next weight step                     │  │
#   │   │   ANY FAIL → AUTOMATIC ROLLBACK (traffic → 100% stable)     │  │
#   │   │                                                              │  │
#   │   └──────────────────────────────────────────────────────────────┘  │
#   │                                                                     │
#   └─────────────────────────────────────────────────────────────────────┘
#
#
# =============================================================================
# COMPONENT MAP
# =============================================================================
#
#   ┌──────────────────┐     scrapes      ┌──────────────────┐
#   │  Nginx Ingress   │ ───────────────▶ │   Prometheus     │
#   │  Controller      │   metrics         │   (monitoring ns)│
#   │  (exposes RPS,   │                   │                  │
#   │   latency, 5xx)  │                   │  Stores:         │
#   └──────────────────┘                   │  - request rate  │
#                                          │  - error rate    │
#   ┌──────────────────┐     scrapes      │  - latency hist  │
#   │  App Pods        │ ───────────────▶ │  - pod restarts  │
#   │  (django-prom)   │   /metrics        └────────┬─────────┘
#   └──────────────────┘                            │
#                                                    │ queries
#                                          ┌─────────▼─────────┐
#                                          │   Argo Rollouts    │
#                                          │   (AnalysisRun)    │
#                                          │                    │
#                                          │   "Is canary OK?"  │
#                                          │   → YES: promote   │
#                                          │   → NO: rollback   │
#                                          └────────────────────┘
#                                                    │
#                                          ┌─────────▼─────────┐
#                                          │     Grafana        │
#                                          │  (visualization)   │
#                                          │                    │
#                                          │  Dashboard shows:  │
#                                          │  - Traffic split   │
#                                          │  - Error comparison│
#                                          │  - Latency trends  │
#                                          └────────────────────┘
#
#
# =============================================================================
# FILES IN THIS SETUP
# =============================================================================
#
# gitops/overlays/prod/
# ├── rollout.yml            — Argo Rollout (replaces Deployment)
# │                            Defines: canary steps, traffic weights, analysis refs
# ├── analysis-template.yml  — AnalysisTemplate + Canary Service
# │                            Defines: Prometheus queries, thresholds, pass/fail
# ├── ingress.yml            — Production Ingress (Argo Rollouts adds canary ingress)
# └── kustomization.yml      — Ties it all together
#
# gitops/observability/
# ├── prometheus-servicemonitor.yml  — ServiceMonitor + PrometheusRule (alerts)
# └── grafana-dashboard.yml         — Dashboard ConfigMap (auto-provisioned)
#
#
# =============================================================================
# HOW AUTO-ROLLBACK WORKS
# =============================================================================
#
# Scenario: New version has a bug causing 10% of requests to return 500.
#
# Timeline:
#   T+0m:  New image tag pushed to Git. ArgoCD syncs. Rollout starts.
#   T+0m:  Canary ReplicaSet created. 5% traffic routed to it.
#   T+1m:  Pause complete. AnalysisRun starts.
#   T+1.5m: Prometheus reports success rate = 90% (threshold: 95%)
#   T+2m:  AnalysisRun result: FAILED (success-rate metric)
#   T+2m:  Argo Rollouts sets canary weight to 0%
#   T+2m:  All traffic back to stable (old version). Users unaffected.
#   T+7m:  Failed canary pods kept for 5 min (debugging), then scaled down.
#
# Result: 95% of users NEVER saw the bug. Only 5% experienced it for ~2 minutes.
# Compare to rolling update: 100% of users see the bug until manual rollback.
#
#
# =============================================================================
# PREREQUISITES — Install Commands
# =============================================================================
#
# 1. Argo Rollouts Controller:
#    helm repo add argo https://argoproj.github.io/argo-helm
#    helm install argo-rollouts argo/argo-rollouts \
#      --namespace argo-rollouts --create-namespace
#
# 2. Prometheus + Grafana (kube-prometheus-stack):
#    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
#    helm install prometheus prometheus-community/kube-prometheus-stack \
#      --namespace monitoring --create-namespace \
#      --set grafana.sidecar.dashboards.enabled=true
#
# 3. Apply observability resources:
#    kubectl apply -f gitops/observability/
#
# 4. Verify Argo Rollouts is working:
#    kubectl argo rollouts dashboard  (opens web UI)
#    kubectl argo rollouts get rollout learneasyai -n project-prod --watch
#
#
# =============================================================================
# GRAFANA ACCESS
# =============================================================================
#
# Default credentials (kube-prometheus-stack):
#   URL: kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring
#   User: admin
#   Pass: kubectl get secret prometheus-grafana -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d
#
# Dashboard: "LearnEasyAI Canary Deployment" (auto-provisioned from ConfigMap)
#
#
# =============================================================================
# USEFUL COMMANDS
# =============================================================================
#
# Watch rollout progress:
#   kubectl argo rollouts get rollout learneasyai -n project-prod --watch
#
# Manually promote canary (skip analysis):
#   kubectl argo rollouts promote learneasyai -n project-prod
#
# Manually abort canary (force rollback):
#   kubectl argo rollouts abort learneasyai -n project-prod
#
# Retry failed rollout:
#   kubectl argo rollouts retry rollout learneasyai -n project-prod
#
# View analysis results:
#   kubectl get analysisrun -n project-prod
#   kubectl describe analysisrun <name> -n project-prod
#
# Check Prometheus metric directly:
#   kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n monitoring
#   → Open http://localhost:9090 → paste query from AnalysisTemplate
#
# =============================================================================
