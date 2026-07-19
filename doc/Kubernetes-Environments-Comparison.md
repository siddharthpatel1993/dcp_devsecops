# Full DevOps Platform — Kubernetes Environments Comparison

## Project: Production-Grade Kubernetes — Self-Managed vs EKS vs OpenShift

**Author:** Siddharth Patel  
**Role:** Staff/Principal DevOps & Cloud Engineer (12 YOE)  
**Technologies:** Kubernetes, AWS EKS, OpenShift, Terraform, Ansible, Prometheus, EFK/ELK

---

## Table of Contents

1. Overview — Why Three Environments?
2. Side-by-Side Comparison (Quick Reference)
3. Self-Managed Kubernetes (kubeadm) — What We Built
4. AWS EKS — Managed Kubernetes
5. OpenShift — Enterprise Kubernetes
6. Deployment Comparison
7. Production Hardening Comparison
8. Monitoring Comparison
9. Logging Comparison
10. Networking Comparison
11. Security Comparison
12. Upgrades & Maintenance Comparison
13. Cost Comparison
14. When to Use Which
15. 3-Tier Application Architecture on Kubernetes (Production)
16. EKS Platform with Terraform (Production Setup)
17. Kubernetes Backup & Disaster Recovery
18. Interview Talking Points

---

## 1. Overview — Why Three Environments?

In 12 years, you'll encounter all three. Each has a place:

| Environment | Think of it as | Best For |
|---|---|---|
| Self-managed (kubeadm) | Building a car from parts | Learning, on-prem, air-gapped, full control |
| EKS | Buying a car (you drive, dealer maintains engine) | AWS-native teams, managed control plane, IRSA |
| OpenShift | Buying a car with chauffeur + insurance | Enterprise/regulated, built-in security, developer platform |

**Simple analogy:**
- kubeadm = you build the house, do plumbing, electrical, everything
- EKS = builder gives you the house, you furnish and maintain it
- OpenShift = move into a managed apartment with security, concierge, maintenance included

---

## 2. Side-by-Side Comparison (Quick Reference)

| Aspect | Self-Managed (kubeadm) | AWS EKS | OpenShift |
|--------|----------------------|---------|-----------|
| Control plane | YOU manage | AWS manages | Red Hat manages (or self-hosted) |
| Cost | EC2 only (~$0) | $73/mo per cluster + EC2 | Subscription ($$$) or ROSA |
| Setup time | Hours (Ansible) | 15 min (eksctl/Terraform) | 45 min (installer) |
| Upgrades | Manual (risky) | Click or API (control plane) | OTA operator (automated) |
| Networking CNI | Your choice (Calico, Flannel) | VPC CNI (native IPs) | OpenShift SDN / OVN-Kubernetes |
| Ingress | Install yourself (Nginx) | AWS ALB Controller | Built-in Router (HAProxy) |
| Registry | Install yourself (Harbor) | ECR (managed) | Built-in internal registry |
| CI/CD | Install yourself (Jenkins) | CodePipeline or external | Built-in Pipelines (Tekton) |
| Monitoring | Install yourself (Prometheus) | Container Insights or self | Built-in (Prometheus + Grafana) |
| Logging | Install yourself (EFK) | CloudWatch/FluentBit | Built-in (EFK pre-configured) |
| Security | PSA/PSS + manual | IRSA + Pod Identity | SCC (Security Context Constraints) |
| RBAC | Configure yourself | OIDC + IAM mapping | Built-in (OAuth + LDAP/AD) |
| Storage | Manual CSI drivers | EBS CSI (managed add-on) | Built-in StorageClasses |
| Multi-tenancy | Manual (namespaces + quotas) | Manual | Projects (enhanced namespaces) |
| Developer UX | kubectl only | kubectl + console | Web console + oc CLI + S2I |
| Compliance | DIY | Shared responsibility | Built-in (FIPS, STIGs, CIS) |

---

## 3. Self-Managed Kubernetes (kubeadm) — What We Built

### Architecture (Our Project)

```
┌─────────────────────────────────────────────────┐
│              CONTROL PLANE (k8smaster)            │
│                                                  │
│  API Server → etcd → Controller Manager         │
│  Scheduler → Calico CNI → CoreDNS               │
│                                                  │
│  EC2: t2.medium (2 vCPU, 4GB)                   │
└───────────────────────┬─────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
┌─────────▼──┐  ┌──────▼─────┐  ┌───▼──────────┐
│  Worker 1   │  │  Worker 2   │  │  Monitoring   │
│  App Pods   │  │  App Pods   │  │  Prometheus   │
│  Fluentd    │  │  Fluentd    │  │  Grafana      │
│  Node-Exp   │  │  Node-Exp   │  │  AlertManager │
└─────────────┘  └─────────────┘  └──────────────┘
```

### How We Deployed (Ansible — 3 playbooks)

**Playbook 1 (all nodes):** Prerequisites
- Disable swap (K8s requirement)
- Load kernel modules: overlay, br_netfilter
- Set sysctl: net.bridge.bridge-nf-call-iptables = 1
- Install containerd with SystemdCgroup = true
- Install kubeadm, kubelet, kubectl (pinned v1.23.4)

**Playbook 2 (master only):** Bootstrap
- `kubeadm init --pod-network-cidr=192.168.0.0/16`
- Copy kubeconfig to ubuntu user ~/.kube/config
- Install Calico CNI (networking between pods)
- Generate join token, save to file

**Playbook 3 (workers):** Join
- Copy join command from master
- Execute `kubeadm join` on each worker
- Verify: `kubectl get nodes` shows Ready

### What's Running After Setup

| Component | How Deployed | Purpose |
|---|---|---|
| Prometheus | Deployment + ConfigMap | Metrics collection |
| Grafana | Deployment + Service | Dashboards |
| AlertManager | Deployment + ConfigMap | Alert routing |
| kube-state-metrics | Deployment + RBAC | K8s object metrics |
| node-exporter | DaemonSet | Node-level metrics |
| ELK | Ansible on dedicated EC2 | Centralized logging |

### Strengths of Self-Managed

- **Full control** — you own everything, can customize anything
- **Deep understanding** — you know exactly how K8s works internally
- **Cost** — no managed service fee ($73/mo saved per cluster)
- **Air-gapped** — works without internet (on-prem, military, banking)
- **Any infrastructure** — bare metal, VMware, any cloud

### Weaknesses (Why We'd Improve)

- **etcd backup** — if master dies without backup, cluster is gone
- **Upgrades** — manual, risky, must follow exact sequence
- **No managed add-ons** — you install/upgrade CNI, CSI, DNS yourself
- **Security patching** — OS + K8s + containerd all your responsibility
- **HA control plane** — need 3 masters + load balancer (complex)


---

## 4. AWS EKS — Managed Kubernetes

### What is EKS?

AWS runs the control plane (API server, etcd, controller manager, scheduler) for you. You only manage worker nodes and what runs on them.

**Simple analogy:** You rent a kitchen (control plane) from a building. The building maintains plumbing and electricity. You bring your own appliances (worker nodes) and cook your food (deploy apps).

### Architecture

```
┌─────────────────────────────────────────────────┐
│        AWS-MANAGED CONTROL PLANE                 │
│  (3 AZs, auto-heals, auto-patches, HA etcd)    │
│                                                  │
│  You NEVER SSH into this. AWS owns it.           │
│  Cost: $73/month flat.                           │
└───────────────────────┬─────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
┌─────────▼──┐  ┌──────▼─────┐  ┌───▼──────────┐
│  Managed    │  │  Managed    │  │  Fargate     │
│  Node Group │  │  Node Group │  │  (serverless)│
│  (AZ-a)     │  │  (AZ-b)     │  │  Per-pod     │
│  m5.large   │  │  m5.large   │  │  No nodes    │
└─────────────┘  └─────────────┘  └──────────────┘
```

### How to Deploy (Terraform)

```hcl
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "prod-cluster"
  cluster_version = "1.28"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets

  eks_managed_node_groups = {
    general = {
      instance_types = ["m5.large"]
      min_size       = 3
      max_size       = 20
      desired_size   = 3
    }
  }
}
```

Time: ~15 minutes. Compare with hours for kubeadm.

### EKS-Specific Features

| Feature | What It Does | Why It Matters |
|---|---|---|
| IRSA | Map K8s ServiceAccount → IAM Role via OIDC | Per-pod AWS permissions, no access keys |
| VPC CNI | Pods get real VPC IPs (not overlay) | Direct communication with AWS services, Security Groups on pods |
| Managed Node Groups | AWS handles AMI updates, drain, replace | Rolling node updates without manual work |
| Fargate | Serverless pods — no nodes to manage | Batch jobs, isolation, zero node maintenance |
| EBS CSI Driver | Managed add-on for persistent volumes | Auto-provisions EBS volumes for StatefulSets |
| ALB Controller | Ingress → creates real AWS ALB | Native WAF integration, path routing |
| Karpenter | Smart node provisioning (~60s) | Right-size nodes, spot instances, bin-packing |

### EKS Strengths

- **Zero control plane ops** — AWS patches, upgrades, HA (3 AZs) automatically
- **AWS integration** — IRSA, ALB, EBS, CloudWatch natively
- **Karpenter** — provisions right-sized nodes in 60 seconds
- **Security** — private API endpoint, envelope encryption, audit logs to CloudTrail
- **Managed add-ons** — VPC CNI, CoreDNS, kube-proxy auto-updated

### EKS Weaknesses

- **Cost** — $73/month control plane + node costs
- **AWS lock-in** — IRSA, VPC CNI, ALB Controller all AWS-specific
- **IP exhaustion** — VPC CNI uses real IPs (can exhaust subnet quickly)
- **Upgrade lag** — AWS releases K8s versions ~2 months after upstream
- **Limited customization** — can't tune API server flags

---

## 5. OpenShift — Enterprise Kubernetes

### What is OpenShift?

Red Hat's enterprise Kubernetes distribution. Includes everything: K8s + CI/CD + monitoring + logging + registry + web console + security hardening. Think "K8s + batteries included + enterprise support."

**Simple analogy:** If K8s is Android (flexible, DIY), OpenShift is iPhone (opinionated, everything works together out of box, locked down by default).

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   OPENSHIFT CLUSTER                       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  CONTROL PLANE (3 masters — always HA)            │   │
│  │  API Server + etcd + Controller + OAuth Server    │   │
│  │  Operator Lifecycle Manager (manages everything)  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  INFRA NODES (dedicated)                          │   │
│  │  Router (HAProxy) + Internal Registry +           │   │
│  │  Prometheus + EFK + Image Builder                 │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  WORKER NODES (application workloads)             │   │
│  │  Your pods run here                               │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### How to Deploy

**On AWS (ROSA — Red Hat OpenShift on AWS):**
```bash
rosa create cluster --cluster-name=prod --region=us-east-1 \
  --machine-pool-min-replicas=3 --machine-pool-max-replicas=20
```

**On-prem (IPI — Installer Provisioned Infrastructure):**
```bash
openshift-install create cluster --dir=./install-config
# Takes ~45 min, creates everything (VMs, DNS, LB, certs)
```

### OpenShift-Specific Features

| Feature | What It Does | K8s/EKS Equivalent |
|---|---|---|
| Routes | Expose apps externally (built-in) | Ingress (must install controller) |
| SCC (Security Context Constraints) | Pod security policies (stricter than PSS) | PodSecurity Admission (weaker) |
| Projects | Enhanced namespaces (quota + RBAC auto-applied) | Namespace + manual quota + RoleBinding |
| Operators (OLM) | Install/upgrade/manage complex apps | Helm + manual lifecycle |
| Internal Registry | Built-in container registry | ECR / Harbor (install separately) |
| S2I (Source-to-Image) | Build images from source without Dockerfile | Docker build + Kaniko |
| OAuth Server | Built-in auth (LDAP, AD, GitHub, Google) | External OIDC setup required |
| Web Console | Rich UI for devs + ops | K8s Dashboard (basic) or Lens |
| Cluster Operators | System components self-manage and self-heal | Manual install + maintain |
| MachineConfig Operator | OS-level config (kernel, sysctl) declaratively | Manual SSH + Ansible |

### OpenShift Strengths

- **Security by default** — runs as non-root, restricted SCC, no privileged pods
- **Everything included** — monitoring, logging, registry, CI/CD, console
- **Operator model** — everything managed by operators (self-healing, auto-upgrade)
- **Enterprise support** — Red Hat 24/7, SLA, certified integrations
- **Compliance** — FIPS 140-2, CIS benchmarks, STIG hardening out of box
- **Developer experience** — web console, S2I, Tekton pipelines built-in

### OpenShift Weaknesses

- **Cost** — subscription expensive ($50K+/year for production)
- **Opinionated** — can't easily swap components (must use their router, registry)
- **Heavyweight** — minimum 3 masters + 3 workers (resource hungry)
- **Version lag** — based on K8s N-1 or N-2 (stability over bleeding edge)
- **Learning curve** — `oc` CLI, Routes vs Ingress, SCC vs PSS, Projects vs Namespaces


---

## 6. Deployment Comparison

### How an Application Gets Deployed

| Step | Self-Managed K8s | EKS | OpenShift |
|------|-----------------|-----|-----------|
| Build image | Docker build + push to DockerHub/Harbor | Docker build + push to ECR | S2I (source-to-image) or Dockerfile → internal registry |
| Store image | Self-hosted registry or DockerHub | ECR (managed, scanning, lifecycle) | Internal registry (built-in, per-project) |
| Define deployment | YAML manifests or Helm | YAML/Helm + ALB Controller annotations | DeploymentConfig or Deployment + Route |
| Deploy method | kubectl apply / ArgoCD | kubectl / ArgoCD / CodeDeploy | oc apply / ArgoCD / Tekton Pipeline |
| Expose externally | Ingress (install Nginx yourself) | Ingress → ALB Controller creates ALB | Route (built-in, auto TLS via cert) |
| TLS | cert-manager + Let's Encrypt (install) | ACM + ALB (native) | Built-in Router handles TLS (auto-provision) |
| Rolling update | Deployment strategy: RollingUpdate | Same | DeploymentConfig has triggers (on image change) |
| Canary | Argo Rollouts (install) | Argo Rollouts (install) | Built-in traffic splitting on Routes |

---

## 7. Production Hardening Comparison

| Hardening Area | Self-Managed K8s | EKS | OpenShift |
|---|---|---|---|
| **Control plane HA** | Manual: 3 masters + HAProxy/kube-vip | Automatic (AWS manages 3 AZs) | Automatic (always 3 masters) |
| **etcd backup** | Manual CronJob + S3 upload | AWS handles (managed etcd) | Automatic (etcd-operator) |
| **Node security** | Manual OS patching (Ansible) | Managed node group AMI updates | MachineConfig Operator (declarative) |
| **Pod security** | PodSecurity Admission (PSA) labels | Same PSA + IRSA | SCC — restricted by DEFAULT (non-root forced) |
| **Network policies** | Install Calico, write policies manually | VPC CNI + Calico/Cilium, write policies | OVN-Kubernetes, default-deny easy via Project |
| **Image policy** | Kyverno/OPA (install + configure) | Same | Built-in image policy (block registries) |
| **Secrets** | External Secrets Operator + Vault | IRSA + Secrets Manager + ESO | Sealed Secrets or Vault + ESO |
| **Audit logging** | Configure API server flags manually | Enabled by default → CloudTrail | Enabled by default → built-in EFK |
| **Certificate rotation** | kubeadm certs auto-renew (1 year) | AWS manages all certs | Automatic (cert operators) |
| **RBAC** | Define all ClusterRoles/Bindings manually | IAM → K8s mapping via aws-auth ConfigMap | OAuth + LDAP integration built-in |
| **Resource limits** | LimitRange + ResourceQuota (manual) | Same | Projects auto-apply quotas on creation |

### Production Checklist (All Environments)

```
□ Non-root containers (runAsNonRoot: true)
□ Read-only root filesystem (readOnlyRootFilesystem: true)
□ Drop all capabilities (drop: ["ALL"])
□ Resource requests AND limits on every pod
□ Liveness + readiness probes on every container
□ Network policies (default-deny + explicit allow)
□ Pod disruption budgets (minAvailable: 2)
□ Anti-affinity (spread replicas across nodes/AZs)
□ Secrets from external store (not K8s Secrets)
□ Image pull from private registry only
□ Signed images verified at admission
□ RBAC — least privilege per ServiceAccount
```

---

## 8. Monitoring Comparison

| Aspect | Self-Managed K8s | EKS | OpenShift |
|---|---|---|---|
| **What we use** | Prometheus + Grafana + AlertManager (manual install) | Container Insights OR Prometheus (self-managed) | Built-in Prometheus + Grafana (pre-configured) |
| **Installation** | Deploy manifests/Helm yourself | Enable add-on OR deploy kube-prometheus-stack | Already installed — zero setup |
| **Node metrics** | node-exporter DaemonSet (install) | CloudWatch Agent OR node-exporter | Built-in (node-exporter pre-deployed) |
| **K8s object metrics** | kube-state-metrics (install) | kube-state-metrics (install) | Built-in (pre-deployed) |
| **Application metrics** | ServiceMonitor CRD (if using Operator) | Same | ServiceMonitor CRD (built-in support) |
| **Dashboards** | Grafana (import/create manually) | CloudWatch dashboards OR Grafana | Built-in Grafana with pre-loaded dashboards |
| **Alerting** | AlertManager → PagerDuty/Slack (configure) | CloudWatch Alarms OR AlertManager | Built-in AlertManager (pre-configured routes) |
| **Scaling metrics** | metrics-server (install) | metrics-server (managed add-on) | Built-in metrics-server |
| **Cost** | Free (self-hosted) | Container Insights = $$$, self-managed = free | Included in subscription |

### What We Monitor (Same Across All)

**Infrastructure (USE method):**
- CPU utilization, memory usage, disk I/O, network per node
- Node conditions (Ready, DiskPressure, MemoryPressure)

**Kubernetes (kube-state-metrics):**
- Pod restarts, pending pods, OOMKilled count
- Deployment replica mismatch (desired vs actual)
- PVC usage %, node allocatable vs requested
- HPA current vs target replicas

**Application (RED method):**
- Request Rate (req/s per service)
- Error Rate (5xx / total requests)
- Duration (latency P50, P95, P99)

**Alerting Strategy (Same Across All):**

| Severity | Condition | Action |
|----------|-----------|--------|
| P1 (page) | Service down, node NotReady >5min, error >5% | PagerDuty → on-call |
| P2 (urgent) | CPU >70% sustained, latency P99 >2s | Slack #alerts |
| P3 (ticket) | Pod restarts >5/hr, disk >80%, cert <14d | Jira auto-ticket |

---

## 9. Logging Comparison

| Aspect | Self-Managed K8s | EKS | OpenShift |
|---|---|---|---|
| **Stack** | EFK (Elasticsearch + Fluentd + Kibana) — install yourself | FluentBit → CloudWatch Logs OR self-managed EFK | Built-in EFK (pre-installed, ClusterLogging CR) |
| **Collection** | Fluentd DaemonSet (install + configure) | FluentBit DaemonSet (aws-for-fluent-bit) | Fluentd DaemonSet (auto-deployed) |
| **Storage** | Elasticsearch (StatefulSet — manage yourself) | CloudWatch Logs (managed, pay per GB) | Elasticsearch (operator-managed) |
| **Visualization** | Kibana (install) | CloudWatch Log Insights OR Kibana | Kibana (built-in, per-project access) |
| **Retention** | Configure yourself (ILM policies) | Set per log group (1 day → never) | Set via ClusterLogging CR (retention per type) |
| **Multi-tenancy** | Manual (index per namespace) | Log group per namespace | Per-project isolation built-in |
| **Setup effort** | Hours (StatefulSet, DaemonSet, ConfigMap, RBAC) | 10 min (enable FluentBit add-on) | Zero (already running) |
| **Cost** | EC2 for ES nodes (storage heavy) | $0.50/GB ingested + storage | Included in subscription |

### What Gets Logged (Same Across All)

| Log Type | Source | Contains |
|----------|--------|----------|
| Application logs | stdout/stderr from containers | Business logic, errors, request traces |
| K8s audit logs | API server | Who did what (kubectl, controllers, users) |
| Node logs | kubelet, containerd | Container lifecycle, image pulls, OOM events |
| Ingress/Router logs | Nginx/ALB/HAProxy | Request path, status code, latency, client IP |

### Log Flow Diagram

**Self-Managed:**
```
Pod stdout → Fluentd DaemonSet → Elasticsearch StatefulSet → Kibana
```

**EKS:**
```
Pod stdout → FluentBit DaemonSet → CloudWatch Logs → Log Insights queries
```

**OpenShift:**
```
Pod stdout → Fluentd (auto-deployed) → Elasticsearch (operator-managed) → Kibana (per-project)
```

---

## 10. Networking Comparison

| Aspect | Self-Managed K8s | EKS | OpenShift |
|---|---|---|---|
| **CNI** | Calico (overlay, supports NetworkPolicy) | VPC CNI (real VPC IPs, no overlay) | OVN-Kubernetes (overlay, full NetworkPolicy) |
| **Pod IPs** | Virtual (192.168.x.x — cluster internal) | Real VPC IPs (10.0.x.x — routable) | Virtual (10.128.x.x — cluster internal) |
| **Service mesh** | Install Istio yourself | Install Istio / App Mesh | Built-in OpenShift Service Mesh (Istio-based) |
| **Ingress** | Install Nginx Ingress Controller | AWS ALB Ingress Controller | Built-in Router (HAProxy) — Route objects |
| **DNS** | CoreDNS (auto-installed by kubeadm) | CoreDNS (managed add-on) | CoreDNS (managed by operator) |
| **Network Policies** | Calico enforces (must install) | Calico or Cilium (install addon) | OVN-Kubernetes enforces (built-in) |
| **Load Balancer** | MetalLB (bare metal) or cloud LB | AWS NLB/ALB (native) | Built-in Router or cloud LB |
| **Multi-cluster** | Manual (Submariner, Skupper) | Transit Gateway + peering | Red Hat ACM (Advanced Cluster Management) |

### EKS VPC CNI — Special Consideration

Pods get real VPC IPs. This means:
- **Pro:** Pods can communicate with AWS services directly (no NAT). Security Groups can be applied per pod.
- **Con:** IP exhaustion. Each EC2 has limited ENIs (m5.large = max 29 pods). Fix: Enable prefix delegation.

```
Without prefix delegation: m5.large = 29 pods max
With prefix delegation:    m5.large = 110 pods max
```

---

## 11. Security Comparison

| Security Area | Self-Managed K8s | EKS | OpenShift |
|---|---|---|---|
| **Default pod security** | Permissive (root allowed unless you enforce) | Permissive (same as vanilla K8s) | RESTRICTED by default (non-root, no privilege escalation) |
| **Pod security enforcement** | PodSecurity Admission (PSA) — label namespaces | Same PSA | SCC (Security Context Constraints) — more granular |
| **IAM for pods** | Service Account tokens (long-lived, broad) | IRSA (short-lived, scoped, per-pod IAM) | STS + bound tokens + workload identity |
| **Image verification** | Kyverno + Cosign (install yourself) | Same (install yourself) | Built-in image signature verification |
| **Secrets encryption** | Enable etcd encryption (manual flag) | Envelope encryption (KMS — enable) | etcd encryption enabled by default |
| **Audit logging** | Configure API server flags | Enabled → CloudTrail (managed) | Enabled by default → EFK |
| **Compliance** | Manual (CIS benchmarks, kube-bench) | CIS EKS Benchmark (shared responsibility) | FIPS 140-2, CIS, STIG certified out-of-box |
| **Vulnerability scanning** | Trivy/Grype (install in CI) | ECR scanning + Inspector | Built-in image scanning + Red Hat Quay |

### SCC vs PSA vs PSS (Key Interview Topic)

**Pod Security Standards (PSS)** — defines 3 profiles:
- Privileged: No restrictions (system components)
- Baseline: Minimal restrictions (most apps)
- Restricted: Hardened (production best practice)

**Pod Security Admission (PSA)** — K8s native enforcement:
```yaml
# Label namespace to enforce restricted profile
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
```

**Security Context Constraints (SCC)** — OpenShift (more powerful):
```
restricted-v2 (default) — non-root, drop ALL caps, read-only FS
anyuid — allows specific UID (for legacy apps)
privileged — full access (only for infra components)
```

**Key difference:** In K8s/EKS, you OPT-IN to security (must label namespaces). In OpenShift, security is DEFAULT — you must opt-OUT to run privileged.


---

## 12. Upgrades & Maintenance Comparison

| Aspect | Self-Managed K8s | EKS | OpenShift |
|---|---|---|---|
| **Control plane upgrade** | Manual: drain master, kubeadm upgrade, uncordon. Risky, 30-60 min downtime risk | AWS API call or click. Zero downtime. 10-15 min | OTA (Over-the-Air) via ClusterVersion operator. Automatic, rolling |
| **Worker node upgrade** | Manual: cordon, drain, upgrade kubelet, uncordon (per node) | Update node group AMI → rolling replacement (automatic) | MachineConfigPool — automatic rolling update of OS + kubelet |
| **Add-on upgrades** | Manual (Calico, CoreDNS, metrics-server each separately) | Managed add-ons auto-update OR manual | Operators auto-upgrade (OLM manages lifecycle) |
| **OS patching** | SSH + yum update (Ansible) | New AMI → node group update | MachineConfig Operator applies OS changes declaratively |
| **Rollback** | Manual: kubeadm downgrade (not recommended) | Not supported for control plane | Automatic rollback if upgrade fails health checks |
| **Version skew** | Your problem (kubelet must be within N-1 of API server) | AWS prevents invalid combinations | Operator prevents invalid upgrades |
| **Frequency** | Quarterly (if disciplined) | AWS pushes: control plane auto-updates in extended support | Monthly (Red Hat releases errata regularly) |

### Upgrade Strategy (Best Practice — All Environments)

1. **Read release notes** — check deprecations, breaking changes
2. **Test in non-prod first** — staging cluster upgraded 1 week before prod
3. **One minor version at a time** — never skip (1.27 → 1.28, not 1.27 → 1.29)
4. **Backup etcd before** — snapshot to S3 (self-managed only)
5. **Verify after** — kubectl get nodes, DaemonSets, HPA, Ingress all working
6. **PDB in place** — ensures app availability during node drain

---

## 13. Cost Comparison

### Monthly Cost for Small Production Cluster (3 workers, HA)

| Component | Self-Managed | EKS | OpenShift (ROSA) |
|---|---|---|---|
| Control plane | 3× m5.large = $210 | $73 flat (managed) | $73 (AWS) + subscription |
| Worker nodes (3× m5.large) | $210 | $210 | $210 |
| Load Balancer | MetalLB (free) or NLB ($20) | ALB ($25) | Router (included) + NLB ($20) |
| Monitoring | Self-hosted (free, uses node resources) | Container Insights ($50) or self-hosted | Included (uses infra nodes) |
| Logging | Self-hosted ES (needs dedicated node $70) | CloudWatch ($100 for 50GB) | Included (uses infra nodes) |
| Red Hat subscription | N/A | N/A | ~$4,000/month |
| **Total** | **~$500-550/month** | **~$560-650/month** | **~$4,500+/month** |

### When Cost Justifies Each

| Budget | Recommendation |
|--------|---------------|
| Startup / Small team | EKS (cheapest managed, least ops burden) |
| Mid-size (own K8s expertise) | Self-managed (save $73/cluster, full control) |
| Enterprise / Regulated | OpenShift (support, compliance, developer platform worth the premium) |
| Mixed workloads | EKS + Fargate (serverless for batch, nodes for steady) |

---

## 14. When to Use Which

| Scenario | Best Choice | Why |
|----------|-------------|-----|
| AWS-native, cloud-first team | **EKS** | IRSA, ALB Controller, Karpenter — tight integration |
| On-premise / air-gapped / bare metal | **Self-managed (kubeadm/kubespray)** | Only option without cloud, full control |
| Enterprise with strict compliance (banking, healthcare) | **OpenShift** | FIPS, STIG, SCC, support SLA, audit trail |
| Developer self-service platform | **OpenShift** | Web console, S2I, built-in pipelines, Projects |
| Multi-cloud (AWS + Azure + GCP) | **Self-managed or Rancher** | Portable, no cloud-specific dependencies |
| Learning / Deep understanding | **Self-managed (kubeadm)** | Learn internals that EKS/OpenShift abstract away |
| Cost-sensitive, small team, AWS | **EKS + Karpenter** | $73/mo control plane, auto-scaling, spot instances |
| Telecom / NFV (5G workloads) | **OpenShift** | CPU pinning, NUMA, SR-IOV, MachineConfig, Red Hat telco expertise |

---

## 15. 3-Tier Application Architecture on Kubernetes (Production)

### How 3-Tier Maps to Kubernetes

```
         INTERNET
            │
    ┌───────▼────────────────────────────────────────┐
    │   WEB TIER (Ingress Controller namespace)       │
    │                                                 │
    │   Ingress Controller (Nginx/ALB) — DaemonSet   │
    │   TLS termination (cert-manager)                │
    │   WAF (ModSecurity or AWS WAF on ALB)          │
    └───────┬─────────────────────────────────────────┘
            │ (ClusterIP Service)
    ┌───────▼────────────────────────────────────────┐
    │   APP TIER (app namespace)                      │
    │                                                 │
    │   Deployment: 3-20 replicas (HPA)              │
    │   Service: ClusterIP (internal only)            │
    │   ServiceAccount: least-privilege               │
    │   PDB: minAvailable: 2                          │
    │   Anti-affinity: spread across nodes/AZs        │
    │   Probes: readiness + liveness                  │
    │   Resources: requests + limits                  │
    └───────┬─────────────────────────────────────────┘
            │ (DB connection via Service/Endpoint)
    ┌───────▼────────────────────────────────────────┐
    │   DATA TIER                                     │
    │                                                 │
    │   Option A: Managed (RDS/CloudSQL — external)  │
    │     → ExternalName Service or Endpoints object  │
    │     → Connection via VPC peering/endpoint       │
    │                                                 │
    │   Option B: In-cluster (StatefulSet)            │
    │     → PostgreSQL StatefulSet (3 replicas)       │
    │     → Headless Service (stable DNS per pod)     │
    │     → PVC per pod (EBS/GP3)                     │
    │     → Backup CronJob → S3                       │
    └─────────────────────────────────────────────────┘
```

### Production K8s Manifests (Key Objects)

| Object | Tier | Purpose |
|---|---|---|
| Ingress | Web | Route external traffic to app Service |
| NetworkPolicy | All | Restrict which pods can talk to which |
| Deployment | App | Stateless app replicas with rolling update |
| HPA | App | Scale pods 3→20 based on CPU/requests |
| PDB | App | Never kill more than 1 pod during drain |
| Service (ClusterIP) | App | Internal load balancing between pods |
| ServiceAccount | App | Pod identity (IRSA on EKS, bound token on OpenShift) |
| ConfigMap | App | Non-secret config (DB host, cache URL) |
| ExternalSecret | App | Sync DB password from Secrets Manager → K8s Secret |
| StatefulSet or ExternalName | Data | Database (in-cluster or external managed) |
| CronJob | Data | Scheduled backups to S3 |

### Network Policies (Micro-segmentation — Same Principle as SG Chaining)

```yaml
# Default: DENY ALL in app namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: app
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]

---
# Allow: Ingress controller → App pods (port 8080 only)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-to-app
  namespace: app
spec:
  podSelector:
    matchLabels:
      app: learneasyai
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - port: 8080

---
# Allow: App pods → Database (port 5432 only)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-app-to-db
  namespace: app
spec:
  podSelector:
    matchLabels:
      app: learneasyai
  egress:
    - to:
        - ipBlock:
            cidr: 10.0.21.0/24  # RDS subnet
      ports:
        - port: 5432
    - to:  # Allow DNS resolution
        - namespaceSelector: {}
      ports:
        - port: 53
          protocol: UDP
```

**Result:** Same security as VPC SG chaining — each tier only talks to adjacent tier. Pod compromised in app tier can reach DB on 5432 but NOTHING else.

### HPA (Auto Scaling — K8s Equivalent of ASG)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: learneasyai-hpa
  namespace: app
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: learneasyai
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "1000"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 100
          periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```

### Database Strategy on K8s

| Approach | When | Pros | Cons |
|---|---|---|---|
| **Managed (RDS/CloudSQL)** — recommended | Production, any size | Auto-failover, auto-backup, patching, scaling handled | Cost, latency (cross-network), vendor lock |
| **StatefulSet (in-cluster)** | Dev/test, on-prem, air-gapped | Full control, no external dependency | You handle backup, failover, upgrades, storage |
| **Operator (CloudNativePG, Zalando)** | Prod in-cluster | Automated failover, backup, replication | Complex, still your responsibility |

**Production recommendation:** Use managed DB (RDS Aurora, Cloud SQL) and connect via:
- EKS: VPC peering + Security Group allowing pod CIDR
- OpenShift: Network egress rules + ExternalName Service
- Self-managed: Direct network (same VPC or VPN)

### 3-Tier on K8s vs 3-Tier on EC2/ASG

| Aspect | EC2/ASG (Project 2) | Kubernetes (Project 3) |
|---|---|---|
| Scaling unit | EC2 instance (minutes) | Pod (seconds) |
| Min overhead | Full VM per instance | Single container per replica |
| Rolling update | ASG instance refresh (80% healthy) | Deployment strategy (maxUnavailable: 0) |
| Load balancer | ALB → Target Group → EC2 | Ingress → Service → Pods |
| Network isolation | Security Groups | Network Policies |
| Secret management | Secrets Manager + IAM role | External Secrets Operator + IRSA |
| Health checks | ALB health check (HTTP) | readiness + liveness probes |
| Cost | Pay per VM (even if underutilized) | Bin-packed (multiple apps per node) |
| Blue-green | Weighted target groups | Argo Rollouts / Ingress canary annotations |
| Observability | CloudWatch Agent + custom metrics | Prometheus ServiceMonitor + auto-discovery |

### Production Topology (EKS Example)

```
┌─────────────────────────────────────────────────────────────┐
│  EKS Cluster (3 AZs)                                        │
│                                                             │
│  Namespace: ingress-system                                  │
│  ├── Ingress Controller (Nginx) — DaemonSet                │
│  ├── cert-manager — auto TLS certs                         │
│  └── ExternalDNS — auto Route53 records                    │
│                                                             │
│  Namespace: app-prod                                        │
│  ├── Deployment: learneasyai (3-20 replicas, HPA)          │
│  ├── Service: ClusterIP                                     │
│  ├── Ingress: host-based routing + TLS                     │
│  ├── NetworkPolicy: allow from ingress only                │
│  ├── PDB: minAvailable: 2                                   │
│  ├── ServiceAccount: annotated with IAM role (IRSA)        │
│  └── ExternalSecret: syncs RDS password from AWS SM        │
│                                                             │
│  Namespace: monitoring                                      │
│  ├── Prometheus (ServiceMonitors auto-discover app)        │
│  ├── Grafana (dashboards per namespace)                    │
│  └── AlertManager (PagerDuty + Slack routing)              │
│                                                             │
│  Namespace: logging                                         │
│  ├── FluentBit DaemonSet → CloudWatch Logs                 │
│  └── (or Loki + Promtail for self-managed)                 │
│                                                             │
│  EXTERNAL (managed):                                        │
│  ├── RDS Aurora (private subnet, SG allows pod CIDR)       │
│  ├── ElastiCache Redis (session store)                     │
│  └── S3 (static assets, backups)                           │
└─────────────────────────────────────────────────────────────┘
```

---

---

## 16. EKS Platform with Terraform (Production Setup)

### Terraform Module Structure

```
terraform/
├── modules/
│   ├── vpc/                  (3 AZs, private subnets for nodes, public for ALB)
│   ├── eks/
│   │   ├── main.tf          (EKS cluster, OIDC provider, managed add-ons)
│   │   ├── node_groups.tf   (managed node groups — on-demand + spot)
│   │   ├── karpenter.tf     (Karpenter provisioner for auto-scaling)
│   │   ├── irsa.tf          (IAM roles for service accounts)
│   │   ├── addons.tf        (VPC CNI, CoreDNS, kube-proxy, EBS CSI)
│   │   └── outputs.tf       (cluster endpoint, OIDC ARN, kubeconfig)
│   ├── helm_releases/
│   │   ├── argocd.tf        (ArgoCD via Helm)
│   │   ├── monitoring.tf    (kube-prometheus-stack via Helm)
│   │   ├── ingress.tf       (Nginx or ALB Controller via Helm)
│   │   ├── cert_manager.tf  (cert-manager via Helm)
│   │   └── external_secrets.tf (ESO via Helm)
│   └── iam/
│       ├── github_oidc.tf   (GitHub Actions → assume role, no keys)
│       └── app_roles.tf     (per-service IAM roles for IRSA)
├── environments/
│   ├── dev/                  (small nodes, spot only, 1 node group)
│   ├── staging/              (prod-like, smaller)
│   └── prod/                 (multi-AZ, on-demand + spot, Karpenter)
└── README.md
```

### EKS Cluster Terraform (Key Resources)

```hcl
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "prod-cluster"
  cluster_version = "1.29"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Private API endpoint (access only from VPC/VPN)
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = false

  # Managed add-ons (AWS auto-updates)
  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true, configuration_values = jsonencode({
      env = { ENABLE_PREFIX_DELEGATION = "true" }  # More pods per node
    })}
    aws-ebs-csi-driver = { most_recent = true, service_account_role_arn = module.ebs_csi_irsa.iam_role_arn }
  }

  # Node groups
  eks_managed_node_groups = {
    # On-demand for critical workloads
    general = {
      instance_types = ["m5.large", "m5a.large"]
      capacity_type  = "ON_DEMAND"
      min_size       = 3
      max_size       = 6
      desired_size   = 3
      labels = { workload = "general" }
    }
    # Spot for non-critical (CI runners, batch)
    spot = {
      instance_types = ["m5.large", "m5a.large", "m5.xlarge", "m4.large"]
      capacity_type  = "SPOT"
      min_size       = 0
      max_size       = 20
      desired_size   = 2
      labels = { workload = "spot" }
      taints = [{ key = "spot", value = "true", effect = "NO_SCHEDULE" }]
    }
  }
}
```

### IRSA (IAM Roles for Service Accounts)

```hcl
# Each microservice gets its own IAM role — no shared credentials
module "order_service_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "order-service-role"

  oidc_providers = {
    main = {
      provider_arn = module.eks.oidc_provider_arn
      namespace_service_accounts = ["app-prod:order-service-sa"]
    }
  }

  role_policy_arns = {
    s3     = aws_iam_policy.order_service_s3.arn      # Read order attachments
    sqs    = aws_iam_policy.order_service_sqs.arn     # Process order queue
    secrets = aws_iam_policy.order_service_secrets.arn # Read DB password
  }
}
```

**Result:** Pod in `app-prod` namespace with ServiceAccount `order-service-sa` can access S3 + SQS + Secrets Manager — nothing else. No access keys, short-lived credentials, CloudTrail auditable.

### Karpenter (Intelligent Node Scaling)

```hcl
# Karpenter replaces Cluster Autoscaler — faster, smarter
resource "helm_release" "karpenter" {
  name       = "karpenter"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = "v0.32.0"
  namespace  = "kube-system"
}
```

**Karpenter NodePool:**
```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand", "spot"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["m5.large", "m5.xlarge", "m5a.large", "c5.large"]
        - key: topology.kubernetes.io/zone
          operator: In
          values: ["us-east-1a", "us-east-1b", "us-east-1c"]
      nodeClassRef:
        name: default
  limits:
    cpu: "1000"    # Max 1000 vCPUs total
  disruption:
    consolidationPolicy: WhenUnderutilized  # Removes underused nodes
    expireAfter: 720h  # Replace nodes every 30 days (fresh AMI)
```

**Karpenter vs Cluster Autoscaler:**

| Aspect | Cluster Autoscaler | Karpenter |
|---|---|---|
| Scaling speed | 2-5 minutes | 30-60 seconds |
| Node type | Fixed per node group | Picks best type for pending pods |
| Bin-packing | Basic | Intelligent (right-sizes to workload) |
| Spot management | One type per group | Multi-type, auto-diversifies |
| Consolidation | Manual | Auto-consolidates underused nodes |
| Setup | Simple (one deployment) | More config (NodePool + NodeClass) |

### Helm for Application Packaging

```
helm-charts/
├── learneasyai/
│   ├── Chart.yaml            (name, version, appVersion)
│   ├── values.yaml           (defaults)
│   ├── values-dev.yaml       (override: 1 replica, small resources)
│   ├── values-staging.yaml   (override: 2 replicas, prod-like)
│   ├── values-prod.yaml      (override: 3-20 replicas, full resources)
│   └── templates/
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── ingress.yaml
│       ├── hpa.yaml
│       ├── pdb.yaml
│       ├── networkpolicy.yaml
│       ├── serviceaccount.yaml
│       └── externalsecret.yaml
```

**values-prod.yaml:**
```yaml
replicaCount: 3
image:
  repository: 123456789.dkr.ecr.us-east-1.amazonaws.com/learneasyai
  tag: "abc123f"  # Git SHA

resources:
  requests:
    cpu: 200m
    memory: 512Mi
  limits:
    cpu: "1"
    memory: 1Gi

hpa:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPU: 60

ingress:
  enabled: true
  host: app.example.com
  tls: true

serviceAccount:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789:role/learneasyai-role
```

### Storage Strategy

| Use Case | Storage Type | K8s Object | AWS Service |
|---|---|---|---|
| Database (if in-cluster) | Block storage | PVC + StorageClass | EBS GP3 (provisioned via EBS CSI) |
| Shared files (uploads, media) | Shared filesystem | PVC (ReadWriteMany) | EFS (mounted across pods/nodes) |
| Static assets | Object storage | Not mounted — accessed via SDK | S3 (direct from app via IRSA) |
| Logs (temporary) | EmptyDir | emptyDir volume | Node disk (ephemeral) |
| Config | ConfigMap/Secret | ConfigMap, ExternalSecret | Secrets Manager (synced via ESO) |

**StorageClass (EBS GP3 — default):**
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer  # Critical — prevents AZ mismatch
parameters:
  type: gp3
  fsType: ext4
  encrypted: "true"
reclaimPolicy: Retain  # Don't delete data on PVC removal
allowVolumeExpansion: true
```

---

## 17. Kubernetes Backup & Disaster Recovery

### What Needs Backup in K8s?

| Component | What's Lost If Gone | Backup Tool |
|---|---|---|
| etcd (self-managed only) | Entire cluster state — all objects gone | etcdctl snapshot |
| Cluster resources (Deployments, Services, ConfigMaps) | App definitions | Velero |
| Persistent Volumes (data) | Application data (DB, uploads) | Velero + CSI snapshots |
| Secrets | Credentials (encrypted in etcd) | External store (Secrets Manager) is the backup |
| Helm releases | Release history, rollback ability | Velero captures or Git is source of truth |

### EKS vs Self-Managed Backup

| Aspect | Self-Managed (kubeadm) | EKS |
|---|---|---|
| etcd backup | YOUR responsibility (CronJob → S3) | AWS manages (you can't access etcd) |
| Cluster resources | Velero | Velero (same) |
| PV snapshots | Velero + CSI snapshots | Velero + EBS snapshots (native) |
| Cluster recreation | kubeadm init (from scratch if etcd lost) | `terraform apply` (recreates in 15 min) |
| Control plane DR | You need 3 masters + restore etcd | AWS handles (multi-AZ built-in) |

### Velero — Cluster Backup & Restore

**What is Velero?** Backs up K8s resources + persistent volumes to S3. Can restore entire namespaces or specific resources.

**Installation (Helm):**
```yaml
# Velero Helm values
configuration:
  backupStorageLocation:
    bucket: company-k8s-backups
    region: us-east-1
  volumeSnapshotLocation:
    provider: aws
    config:
      region: us-east-1
schedules:
  daily-full:
    schedule: "0 2 * * *"           # 2 AM daily
    template:
      includedNamespaces: ["*"]      # All namespaces
      excludedNamespaces: ["kube-system"]
      ttl: 168h                      # Keep 7 days
      snapshotVolumes: true          # Include PV data
```

**Backup types:**

| Type | What | When | Retention |
|---|---|---|---|
| Scheduled full | All namespaces + PVs | Daily 2 AM | 7 days |
| Pre-upgrade | Full cluster state | Before K8s version upgrade | 30 days |
| Namespace | Single app namespace | Before risky deploy | 48 hours |
| On-demand | Specific resources | Before manual changes | Until deleted |

### Disaster Scenarios & Recovery

| Scenario | Recovery | RTO | Tool |
|---|---|---|---|
| **Namespace accidentally deleted** | `velero restore --from-backup daily --include-namespaces app-prod` | 5 min | Velero |
| **Cluster corrupted/unreachable** | `terraform apply` (new cluster) → `velero restore` (all resources) | 20 min | Terraform + Velero |
| **PV data lost** | Restore from Velero volume snapshot | 10 min | Velero CSI snapshots |
| **Region failure** | Terraform creates EKS in DR region → Velero restore from cross-region S3 | 30 min | Terraform + Velero + S3 CRR |
| **Bad deployment (app-level)** | `helm rollback` or ArgoCD git revert (no Velero needed) | 1 min | Helm/ArgoCD |
| **etcd corrupted (self-managed)** | Restore etcd snapshot: `etcdctl snapshot restore` | 15 min | etcdctl |

### etcd Backup (Self-Managed Only)

```yaml
# CronJob running on master node
apiVersion: batch/v1
kind: CronJob
metadata:
  name: etcd-backup
  namespace: kube-system
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          hostNetwork: true
          containers:
          - name: backup
            image: bitnami/etcd:3.5
            command:
            - /bin/sh
            - -c
            - |
              etcdctl snapshot save /backup/etcd-$(date +%Y%m%d-%H%M).db \
                --endpoints=https://127.0.0.1:2379 \
                --cacert=/etc/kubernetes/pki/etcd/ca.crt \
                --cert=/etc/kubernetes/pki/etcd/server.crt \
                --key=/etc/kubernetes/pki/etcd/server.key
              aws s3 cp /backup/ s3://company-etcd-backups/ --recursive
          restartPolicy: OnFailure
```

### Multi-Cluster DR Strategy

```
PRIMARY CLUSTER (us-east-1)         DR CLUSTER (eu-west-1)
┌─────────────────────┐            ┌─────────────────────┐
│  EKS Cluster        │            │  EKS Cluster        │
│  (full workload)    │            │  (standby — scaled  │
│                     │            │   to zero or min)   │
│  Velero → S3 ──────────CRR──────▶  S3 (backup copy)  │
│                     │            │                     │
│  ArgoCD (active)    │            │  ArgoCD (synced but │
│                     │            │   suspended apps)   │
└─────────────────────┘            └─────────────────────┘

On failure:
1. Activate DR ArgoCD apps (unsuspend)
2. Velero restore PVs from S3 replica
3. Update Route53 / Global Accelerator to DR
4. Scale up node groups
RTO: ~15-20 minutes
```

### Interview Quick Answer

**Q: "How do you handle K8s disaster recovery?"**

A: Two layers. For app-level issues (bad deploy), ArgoCD git revert or Helm rollback — takes 30 seconds. For cluster-level disasters, Velero backs up all resources + PV snapshots to S3 daily, with cross-region replication. Full cluster recovery = Terraform recreates EKS (15 min) + Velero restores workloads (5 min). For self-managed clusters, we also back up etcd every 6 hours to S3. Quarterly DR drills prove we can restore a full cluster from zero in under 20 minutes.

**Q: "Velero vs just using GitOps for recovery?"**

A: GitOps (ArgoCD) recovers your Deployments, Services, ConfigMaps — everything defined in Git. But it does NOT recover: PersistentVolume data, Secrets not in Git, CRDs, and cluster-level resources not managed by ArgoCD. Velero fills that gap — it captures everything including PV data. Best practice: ArgoCD for app resources (fast, git-based), Velero for data + cluster-level objects (safety net).

---

## 18. Interview Talking Points

### 2-Minute Version (for "Tell me about Kubernetes")

"I've worked with Kubernetes across three environments. Built a full platform from scratch using kubeadm — bootstrapped the cluster, installed Calico CNI, deployed the entire Prometheus monitoring stack as manifests. This gave me deep understanding of K8s internals. In production we use EKS with Terraform — IRSA for pod-level IAM, Karpenter for intelligent node scaling, ALB Controller for ingress, ArgoCD for GitOps deployments. I've also operated OpenShift in telecom environments where compliance requirements demanded SCCs, CPU pinning for NFV workloads, and the built-in EFK logging stack. I can compare trade-offs across all three and recommend based on team capability, compliance needs, and budget."

### Common Follow-Up Questions

**Q: Why kubeadm when EKS exists?**  
A: Two reasons. First, deep understanding — knowing how etcd, the scheduler, and kubelet work together helps me troubleshoot EKS issues that most people can't. Second, on-prem and air-gapped environments don't have EKS. Telecom clients needed K8s without internet access.

**Q: How do you handle EKS upgrades?**  
A: One minor version at a time. Upgrade control plane first (API call, zero downtime), then update managed node groups (rolling — new nodes join, old drain/terminate). Always test in staging first, verify add-ons (CNI, CSI, CoreDNS) compatibility. PDBs ensure app availability during node drain.

**Q: What's the biggest difference between OpenShift and K8s?**  
A: Security posture. In vanilla K8s, everything is permissive by default — you must add restrictions. In OpenShift, everything is restricted by default — pods can't run as root, can't use privileged mode. You explicitly grant permissions. This is why regulated industries prefer it — secure from day one, not secure after hardening.

**Q: How do you decide which to use for a new project?**  
A: Three questions: (1) Where does it run? Cloud-only → EKS. On-prem → kubeadm/OpenShift. (2) Compliance requirements? SOC2/PCI basic → EKS + proper RBAC. FIPS/STIG/FedRAMP → OpenShift. (3) Team capability? Small team without K8s depth → EKS (less ops). Large platform team → self-managed (full control, cheaper).

**Q: How is monitoring different across the three?**  
A: Same Prometheus stack, different installation effort. Self-managed = you deploy everything (manifests or Helm). EKS = you deploy it but can also use Container Insights (simpler, costly). OpenShift = already running on day one, pre-configured dashboards, per-project access. The metrics collected and alerting strategy are identical regardless of platform.

**Q: Have you used service mesh?**  
A: Yes. On self-managed K8s we installed Istio manually — mTLS strict mode, traffic splitting for canary, Kiali for topology. On EKS, same approach (Istio or App Mesh). On OpenShift, it's available as a built-in operator (OpenShift Service Mesh). The concepts (mTLS, VirtualService, DestinationRule) are identical across all three — just the installation method differs.

---

## Summary

| What This Document Proves | Interview Value |
|---|---|
| Built K8s from scratch (kubeadm) | "I understand internals, not just managed services" |
| Operated EKS in production | "I know AWS-native K8s patterns (IRSA, Karpenter, ALB)" |
| Worked with OpenShift | "I handle enterprise/regulated environments" |
| Can compare all three | "I recommend the right tool based on context, not preference" |
| Monitoring same across all | "Platform changes, observability principles don't" |
| Security differences | "I know SCC vs PSA vs IRSA — and when each matters" |

This is your **single reference document** for all Kubernetes questions in interviews. Whether they ask about kubeadm internals, EKS node groups, or OpenShift SCCs — you have the answer.
