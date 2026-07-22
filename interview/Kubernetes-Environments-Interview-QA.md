# Interview Q&A Bank: Kubernetes Environments Comparison

## Project: Production-Grade Kubernetes — Self-Managed (kubeadm) vs EKS vs OpenShift

**Technologies:** Kubernetes, kubeadm, AWS EKS, OpenShift, Terraform, Ansible, Calico, VPC CNI, Karpenter, IRSA, Prometheus, EFK, Velero, ArgoCD, Helm

---

## Section 1: Project Story (STAR Format)

### Q1: Walk me through your Kubernetes experience in 2 minutes.

**Answer:**
Worked with Kubernetes across three environments. Built a self-managed cluster from scratch using kubeadm — bootstrapped control plane, configured Calico CNI, deployed full Prometheus monitoring stack via manifests. This gave me deep understanding of K8s internals (etcd, scheduler, kubelet interactions). In production, we use EKS with Terraform — IRSA for per-pod IAM, Karpenter for intelligent node scaling in 60 seconds, ALB Controller for native AWS ingress, VPC CNI with prefix delegation for pod density. Also operated OpenShift in telecom environments where compliance demanded SCCs, CPU pinning for NFV workloads, and built-in EFK logging. I can compare trade-offs across all three and recommend based on team capability, compliance needs, and budget.

---

### Q2: Why did you work with all three instead of just picking one?

**Answer:**
- **Situation:** Different clients/projects had different constraints. Banking client: on-prem only (no cloud). SaaS product: AWS-native, speed-to-market priority. Telecom: FIPS/STIG compliance required.
- **Task:** Provide the right K8s platform for each context, not force one tool everywhere.
- **Action:** Built kubeadm for on-prem/air-gapped, EKS for cloud-native, operated OpenShift for regulated telecom.
- **Result:** Each environment runs reliably. My ability to compare all three makes me uniquely effective — I don't just say "use EKS" without considering if it's the right fit.

---

### Q3: What was the most challenging Kubernetes problem you solved?

**Answer:**
EKS VPC CNI IP exhaustion. With default VPC CNI, each pod gets a real VPC IP. On m5.large instances, maximum ~29 pods per node (limited by ENIs). Our microservices deployment needed 80+ pods per node for cost efficiency.

**Fix:** Enabled prefix delegation (`ENABLE_PREFIX_DELEGATION=true`). This assigns /28 prefixes instead of individual IPs — jumped from 29 to 110 pods per node. Also required: adjusting max-pods setting in kubelet, updating subnet CIDRs to have enough IPs, and testing that Security Groups on pods still worked correctly.

**Impact:** Reduced our node count from 12 to 5 for the same workload. Saved ~$500/month.

---

### Q4: What trade-offs did you accept in each environment?

**Answer:**
| Environment | Accepted Trade-off | Why It Was OK |
|---|---|---|
| Self-managed | Manual upgrades (risky, time-consuming) | Full control needed for air-gapped; team had deep K8s skills |
| EKS | AWS lock-in (IRSA, VPC CNI, ALB Controller all AWS-specific) | Already all-in on AWS; portability not a requirement |
| OpenShift | High cost ($50K+/year subscription) | Client's compliance requirement justified it; 24/7 Red Hat support included |
| EKS | $73/mo per cluster (vs free kubeadm) | Zero control plane ops worth far more than $73/month in engineer time |

---

## Section 2: Technical Deep-Dive (How It Works Under the Hood)

### Q5: Explain how kubeadm bootstraps a cluster. What happens internally?

**Answer:**
`kubeadm init` does the following in sequence:
1. **Preflight checks:** Validates CPU/RAM requirements, checks port availability, verifies container runtime running.
2. **Certificate generation:** Creates CA, API server cert, kubelet certs, etcd certs — all under `/etc/kubernetes/pki/`.
3. **kubeconfig creation:** Generates admin, controller-manager, scheduler kubeconfigs.
4. **Static pod manifests:** Writes API server, etcd, controller-manager, scheduler manifests to `/etc/kubernetes/manifests/`. Kubelet watches this directory → starts them as static pods.
5. **etcd bootstrap:** Single-node etcd starts, stores initial cluster state.
6. **API server starts:** Listens on 6443, uses generated certs.
7. **Apply addons:** CoreDNS, kube-proxy deployed as manifests.
8. **Generate join token:** Token for workers to authenticate with API server.

Workers then run `kubeadm join` — kubelet contacts API server with token, gets approved, downloads kubelet config, starts running pods.

**Key insight:** After kubeadm init, there's NO pod networking yet. Pods can't communicate across nodes until you install a CNI (Calico, Flannel). That's why the next step is always `kubectl apply -f calico.yaml`.

---

### Q6: How does IRSA (IAM Roles for Service Accounts) work internally?

**Answer:**
```
Pod with ServiceAccount → mounts projected token → 
  calls AWS API → STS AssumeRoleWithWebIdentity →
  EKS OIDC provider verifies token → 
  returns temporary credentials (15 min)
```

**Step by step:**
1. EKS creates an OIDC identity provider (auto-configured at cluster creation).
2. You create an IAM role with trust policy: "Trust tokens from this OIDC provider, for ServiceAccount X in namespace Y."
3. Annotate the K8s ServiceAccount with `eks.amazonaws.com/role-arn: arn:aws:iam::123:role/my-role`.
4. When pod starts, EKS webhook mutates the pod spec — injects a projected token volume + AWS env vars.
5. AWS SDK in the pod uses the projected token to call `sts:AssumeRoleWithWebIdentity`.
6. STS validates the token against the OIDC provider → returns temporary creds (15 min lifetime).
7. Pod uses creds to access AWS services (S3, SQS, etc.) — scoped to that role's permissions.

**Why this matters:** No access keys stored anywhere. Per-pod granularity (not per-node). Short-lived. CloudTrail auditable. If pod is compromised, blast radius is limited to that one role's permissions.

---

### Q7: How does Karpenter differ from Cluster Autoscaler internally?

**Answer:**
**Cluster Autoscaler:**
1. Watches for pods in `Pending` state (can't be scheduled).
2. Checks if any existing node group can scale up.
3. Adds a node to the appropriate node group (fixed instance type per group).
4. Takes 2-5 minutes (AWS API → EC2 launch → node registration → pod scheduled).

**Karpenter:**
1. Watches for pods in `Pending` state.
2. Analyzes pending pod requirements (CPU, memory, GPU, topology, affinity).
3. Selects the BEST instance type from a list (considers spot pricing, available capacity).
4. Launches an instance directly (no node group — raw EC2 fleet API).
5. Takes 30-60 seconds.
6. **Consolidation:** Periodically checks — "Can I replace 3 underused m5.large with 1 m5.xlarge?" → yes → does it.

**Key differences:**
| Aspect | Cluster Autoscaler | Karpenter |
|---|---|---|
| Instance selection | Fixed per node group | Dynamic per pod needs |
| Bin-packing | Basic | Intelligent (right-sizes to workload) |
| Speed | 2-5 min | 30-60 sec |
| Spot management | One type per node group | Multi-type diversification |
| Consolidation | None | Auto-consolidates underused nodes |
| Node expiry | None | `expireAfter: 720h` (fresh AMIs) |

---

### Q8: How does OpenShift SCC differ from Kubernetes PSA (Pod Security Admission)?

**Answer:**
**PSA (K8s native):**
- Labels namespaces with profiles: `privileged`, `baseline`, `restricted`.
- Binary: namespace is enforced at ONE level.
- Limited granularity: can't say "allow this specific pod to be different."
- Must opt-in (label namespaces manually).

**SCC (OpenShift):**
- Applied at CLUSTER level, matched by ServiceAccount/user/group.
- Multiple SCCs with priority ordering — most restrictive matching SCC wins.
- Granular: can allow specific UIDs, specific capabilities, specific volume types.
- Opt-OUT model: `restricted-v2` SCC is DEFAULT. Pods MUST run as non-root unless explicitly granted `anyuid` SCC.

**Example difference:**
```
K8s/EKS: Pod runs as root by default (unless you add securityContext)
OpenShift: Pod FAILS to schedule by default if it requires root (must grant SCC)
```

**Interview key point:** OpenShift is "secure by default" — you grant permissions. K8s is "permissive by default" — you restrict access. This is why regulated industries prefer OpenShift.

---

### Q9: Explain VPC CNI vs Calico overlay networking.

**Answer:**
**Calico (overlay — self-managed/OpenShift):**
- Pods get IPs from a virtual CIDR (e.g., 192.168.0.0/16) — NOT real VPC IPs.
- Traffic between nodes is encapsulated (VXLAN or IP-in-IP tunnels).
- Node A pod (192.168.1.5) → encapsulate → Node B → decapsulate → Pod (192.168.2.10).
- **Pro:** No IP exhaustion risk, works on any infrastructure.
- **Con:** Slight overhead from encapsulation, pods can't directly communicate with AWS services via VPC routing.

**VPC CNI (EKS):**
- Pods get real VPC IPs (from your subnet CIDR, e.g., 10.0.11.0/24).
- No overlay, no encapsulation. Pod IP is routable within VPC.
- **Pro:** Pods can use Security Groups directly, communicate with RDS/ElastiCache without NAT, native performance.
- **Con:** IP exhaustion risk (each pod = 1 IP from subnet). Fix: prefix delegation (110 pods/node instead of 29).

**When each matters:**
- Need pods to reach AWS services directly (SG rules on pod IP) → VPC CNI.
- On-prem or multi-cloud (no VPC) → Calico.
- Very high pod density → Calico (no IP limits) or VPC CNI + prefix delegation.

---

### Q10: How do you deploy a 3-tier app differently on K8s vs EC2/ASG?

**Answer:**
| Aspect | EC2/ASG (VM approach) | Kubernetes |
|---|---|---|
| Web tier | ALB → Target Group → EC2 instances | Ingress → Service → Pods |
| Scaling | ASG (minutes to launch VM) | HPA (seconds to add pod) |
| Isolation | Security Groups (network) | NetworkPolicy (namespace/label) |
| Deployment | AMI swap → instance refresh | Image tag update → rolling update |
| Service discovery | ALB DNS or Route53 | K8s DNS (`svc.namespace.svc.cluster.local`) |
| Secrets | Secrets Manager + IAM role at boot | ExternalSecret Operator → K8s Secret |
| Health check | ALB health check (HTTP) | Readiness + liveness probes |
| Cost per unit | Full VM (even if 10% utilized) | Shared node (bin-packed, multiple apps) |
| Rollback | Revert launch template + instance refresh (5 min) | `kubectl rollout undo` (30 sec) |

**Key advantage of K8s:** Multiple microservices share the same nodes (bin-packing). On EC2, each service needs its own ASG → wasted capacity.

---

### Q11: How does EKS managed node group rolling update work?

**Answer:**
1. You update the launch template (new AMI or config).
2. EKS detects the change → starts update.
3. For each node (one at a time):
   a. **Cordon** the node (no new pods scheduled).
   b. **Drain** the node (`kubectl drain` — evicts pods respecting PDBs).
   c. PDB ensures minimum pods stay running on OTHER nodes.
   d. **Terminate** the old node.
   e. **Launch** new node with updated AMI.
   f. New node joins cluster, passes health checks.
   g. Pods scheduled onto new node.
4. Repeat for all nodes.

**Key configs:**
- `updateConfig.maxUnavailable: 1` — only 1 node updated at a time.
- PDBs critical — without them, drain can kill all replicas.
- `force_update_version: true` — force even if PDB violated (dangerous, avoid).

**Total time:** 3 nodes × ~5 min each = ~15 minutes for a small cluster.

---

### Q12: What happens when a pod's readiness probe fails vs liveness probe fails?

**Answer:**
| | Readiness Probe Failure | Liveness Probe Failure |
|---|---|---|
| What K8s does | Removes pod from Service endpoints | Restarts the container |
| Traffic impact | No NEW traffic to this pod | Container killed + restarted |
| Pod stays running? | ✅ Yes (just not in Service) | ❌ No (restarted) |
| Use case | App temporarily busy/initializing | App deadlocked/hung |
| During deploy | New pod not ready yet → no traffic until ready | N/A (wouldn't fail immediately) |

**Real scenario:** During rolling update, new pod starts → readiness probe fails for 10s (app initializing JVM) → K8s waits → probe passes → pod added to Service → old pod terminated. Users never see errors because traffic only goes to ready pods.

**Common mistake:** Making liveness probe too aggressive → pod restarts during temporary load spike → reduces capacity → more load on remaining pods → cascade failure. Set liveness timeout generously (30s+).



---

## Section 3: Troubleshooting Scenarios

### Q13: Pods are stuck in Pending state. Walk me through debugging.

**Answer:**
1. `kubectl describe pod <name>` → check Events section.
2. **Common causes:**
   - **Insufficient resources:** "0/5 nodes available: 3 Insufficient cpu, 2 Insufficient memory." Fix: Reduce requests, add nodes, or check if Karpenter/CA is stuck.
   - **No matching node:** Affinity/nodeSelector requires label that no node has. Fix: Label a node or remove constraint.
   - **Taint not tolerated:** Node has taint (e.g., `spot=true:NoSchedule`), pod doesn't tolerate it.
   - **PVC pending:** StorageClass can't provision volume. Check `kubectl describe pvc` → SC exists? Quota hit? Wrong AZ (WaitForFirstConsumer)?
   - **Unschedulable nodes:** All nodes cordoned (during upgrade/maintenance).
3. **Karpenter-specific:** Check Karpenter controller logs — `kubectl logs -n kube-system karpenter-xxx`. Is NodePool configured? Hitting limits? Spot capacity unavailable?

---

### Q14: Application is deployed but returning 503 from Ingress. What do you check?

**Answer:**
1. **Pod health:** `kubectl get pods` — are pods Running and Ready (1/1)?
   - If 0/1 Ready → readiness probe failing. Check probe config + app startup.
2. **Service endpoints:** `kubectl get endpoints <svc-name>` — are pods listed?
   - Empty endpoints = selector doesn't match pod labels.
3. **Ingress → Service connection:** `kubectl describe ingress` → check backend service name and port match.
4. **Service port vs container port:** Service targetPort must match container's exposed port.
5. **NetworkPolicy:** Is there a default-deny policy blocking ingress controller → app communication?
6. **Ingress controller logs:** `kubectl logs -n ingress-nginx <controller-pod>` → shows upstream errors.

**Most common cause:** Service selector labels don't match pod labels (typo in label key/value). Second most common: readiness probe failing (app not ready but deployed).

---

### Q15: EKS cluster upgrade failed midway — some nodes on 1.28, some on 1.29. What do you do?

**Answer:**
1. **Don't panic.** K8s supports N-1 version skew (kubelet 1.28 can talk to API server 1.29). It's operating within spec.
2. **Check control plane:** `kubectl version --short` → API server version. If control plane upgraded successfully, it's stable.
3. **Check stuck nodes:** `kubectl get nodes` → which nodes are old version?
4. **Common cause of stuck upgrade:** PDB blocking drain. Pod can't be evicted because PDB says `minAvailable: 3` and only 3 replicas exist (need at least 4 for drain).
5. **Fix PDB:** Temporarily increase replica count (3→4), or relax PDB during upgrade window.
6. **Retry node group update:** `aws eks update-nodegroup-version` — it'll continue from where it stopped.
7. **If truly stuck:** Cordon old nodes manually, drain with `--delete-emptydir-data --force` (last resort), terminate, let ASG replace.

**Prevention:** Always test upgrades in staging first. Ensure PDBs allow at least 1 pod to be unavailable.

---

### Q16: Pod keeps restarting (CrashLoopBackOff). How do you debug?

**Answer:**
1. `kubectl logs <pod> --previous` — see crash logs from LAST container (before restart).
2. `kubectl describe pod <pod>` → check:
   - Exit code: 137 = OOMKilled (memory limit too low). 1 = app error. 143 = SIGTERM (graceful shutdown failed).
   - Last state reason: "OOMKilled" vs "Error" vs "Completed".
3. **OOMKilled (exit 137):** Increase memory limit. Check if app has memory leak (`kubectl top pod` over time).
4. **App error (exit 1):** Read logs — missing env var? Can't connect to DB? Config error?
5. **Liveness probe killing it:** Pod starts → liveness check too early → fails → restart → loop. Fix: increase `initialDelaySeconds`.
6. **Debug with ephemeral container:** `kubectl debug -it <pod> --image=busybox -- sh` (K8s 1.25+).

---

### Q17: Nodes are NotReady in your self-managed cluster. What's your approach?

**Answer:**
1. `kubectl describe node <name>` → check Conditions (MemoryPressure, DiskPressure, PIDPressure, NetworkUnavailable).
2. **SSH to the node** → check kubelet: `systemctl status kubelet`, `journalctl -u kubelet -f`.
3. **Common causes:**
   - Kubelet crashed: `systemctl restart kubelet`.
   - Certificate expired (kubeadm certs valid 1 year): `kubeadm certs check-expiration`, renew.
   - Disk full: `/var/lib/containerd` filling up with images. Clean with `crictl rmi --prune`.
   - CNI plugin crashed: Calico pods not running on that node → check DaemonSet.
   - Clock skew: Certificate validation fails. Fix NTP (`chronyd`).
4. **If unfixable:** Cordon, drain, terminate node, replace with fresh one.
5. **Prevention (EKS):** Managed node groups — AWS handles node health, auto-replaces unhealthy.

---

### Q18: Network policies are blocking traffic you expect to be allowed. How do you debug?

**Answer:**
1. **Check if default-deny exists:** `kubectl get networkpolicy -n <namespace>`. If there's a policy selecting `podSelector: {}` → it denies everything not explicitly allowed.
2. **Check pod labels:** Does the allow policy's `podSelector` match your pod's labels exactly? One typo = no match = blocked.
3. **Check namespace labels:** If using `namespaceSelector`, verify the source namespace has the required label.
4. **Test connectivity from inside pod:** `kubectl exec -it <pod> -- curl <target-svc>:port`. Shows if it's network policy or something else.
5. **CNI-specific tools:**
   - Calico: `calicoctl get networkpolicy -n <ns>` → shows compiled rules.
   - Cilium: `cilium monitor` → shows allowed/dropped packets in real-time.
6. **Common mistake:** NetworkPolicy uses labels on the SERVICE name instead of on the POD. Policies match pods, not services.

---

### Q19: Velero backup succeeds but restore fails with "PV not found." What's wrong?

**Answer:**
1. **Volume snapshot vs file-level backup:** Velero uses CSI volume snapshots. If snapshot was in us-east-1a but you're restoring in us-east-1b → snapshot not available in that AZ.
2. **StorageClass mismatch:** Backup had StorageClass `gp2`, restore cluster only has `gp3`. Fix: use `--storage-class-mapping gp2:gp3` flag.
3. **PV reclaim policy:** If original PV had `reclaimPolicy: Retain` and the PV still exists (from previous restore attempt) → conflict. Delete the old PV first.
4. **Cross-region restore:** Volume snapshots don't cross regions. Need to copy snapshot to DR region first, or use Velero's `BackupStorageLocation` with file-level backup (restic/kopia).
5. **Fix:** `velero restore create --from-backup daily --restore-volumes=true --namespace-mappings old-ns:new-ns`.

---

## Section 4: System Design (Architecture-Level Thinking)

### Q20: Design a multi-tenant Kubernetes platform for 10 teams.

**Answer:**

**Requirements clarified:** 10 teams, separate workloads, cost attribution, isolation, self-service deployment.

**Architecture:**
```
EKS Cluster (shared)
├── Namespace per team (team-a, team-b, ...)
├── ResourceQuota per namespace (CPU/memory limits)
├── LimitRange per namespace (default requests/limits per pod)
├── NetworkPolicy: default-deny between namespaces
├── RBAC: Team A can only access team-a namespace
├── ArgoCD AppProject per team (restricts what they can deploy)
└── Karpenter NodePool per team (optional — workload isolation on nodes)
```

**Key design decisions:**
1. **Namespace isolation** (not separate clusters) — cost-effective, shared infra.
2. **NetworkPolicy default-deny** between namespaces — team-a can't reach team-b pods.
3. **ResourceQuota** — team can't consume entire cluster.
4. **RBAC via OIDC** — each team's IAM role maps to K8s RBAC (view own namespace only).
5. **Cost:** Kubecost labels costs per namespace → chargeback to teams.
6. **Shared services:** Monitoring, logging, ingress in dedicated namespaces.

**When to use separate clusters instead:** If teams need different K8s versions, compliance requires hard isolation (not just namespace), or blast radius of shared cluster is too high.

---

### Q21: Design a Kubernetes DR strategy for a stateful application.

**Answer:**

**Requirements:** StatefulSet with PostgreSQL, RPO < 5 min, RTO < 30 min.

**Architecture:**
```
Primary Cluster (us-east-1)         DR Cluster (us-west-2)
├── StatefulSet: postgres (3 pods)   ├── StatefulSet: postgres (0 pods — standby)
├── PVCs → EBS GP3 volumes           ├── PVCs → restored from snapshots
├── Velero → S3 (backup every 5 min) ├── Velero restore from S3 CRR
├── CronJob: WAL archive → S3        ├── WAL replay on failover
└── ArgoCD: active apps               └── ArgoCD: suspended apps
```

**Failover process:**
1. Detect primary failure (health check on Ingress endpoint).
2. Activate DR cluster: unsuspend ArgoCD apps.
3. Velero restore PVCs from latest snapshot (< 5 min old).
4. PostgreSQL replays WAL logs from S3 (point-in-time recovery).
5. Scale StatefulSet to 3 replicas.
6. Update Route53/Global Accelerator to DR cluster.
7. RTO achieved: ~20 minutes.

**Alternative (better RPO):** Use managed DB (RDS Aurora Global) external to K8s. K8s handles only stateless app tier. DB failover is independent and faster (<30s).

---

### Q22: How would you migrate from self-managed kubeadm to EKS without downtime?

**Answer:**

**Strategy:** Parallel run with traffic shifting (same as EC2→ECS migration pattern).

1. **Phase 1 — Setup:** Create EKS cluster via Terraform. Deploy same app with same image tags.
2. **Phase 2 — Data:** If using in-cluster DB → migrate to RDS (external). Both clusters connect to same RDS.
3. **Phase 3 — Traffic split:** Route53 weighted routing: 90% → old cluster ingress, 10% → EKS ingress.
4. **Phase 4 — Validate:** Monitor error rates, latency on EKS portion. Fix any issues.
5. **Phase 5 — Shift:** 50/50, then 90% EKS, 10% old. Then 100% EKS.
6. **Phase 6 — Decommission:** Tear down old kubeadm cluster after 1 week stability.

**Zero downtime guarantee:** At every step, both clusters serve traffic. DNS-level shifting (not application-level).

**Key risks:** Different CNI behavior (Calico overlay vs VPC CNI real IPs), IRSA setup (doesn't exist in kubeadm), Ingress differences (Nginx vs ALB Controller). Test thoroughly in staging first.

---

### Q23: Design the Kubernetes platform observability stack.

**Answer:**
```
Metrics:   Prometheus (kube-prometheus-stack via Helm)
           └── ServiceMonitor auto-discovers app metrics
           └── AlertManager → PagerDuty (P1) / Slack (P2)
           └── Grafana dashboards (per namespace, per service)

Logs:      FluentBit DaemonSet → CloudWatch Logs (EKS)
           OR FluentBit → Loki (self-managed, cheaper)
           └── Structured JSON, indexed by namespace/pod/container

Traces:    OpenTelemetry Collector → Tempo or Jaeger
           └── Per-request trace across microservices
           └── Identifies: which service is the bottleneck?

Cost:      Kubecost → per-namespace, per-team cost attribution
           └── Alert: "team-a exceeding $500/month budget"

Cluster:   kube-state-metrics → pod restarts, pending pods, PVC usage
           node-exporter → CPU, memory, disk, network per node
```

**Alert strategy:** Same across all K8s flavors — alert on symptoms (error rate, latency), not causes (CPU). "5xx > 5% for 2 min" = page. "CPU > 70% for 5 min" = auto-scale (not alert).



---

## Section 5: Comparison & Decision-Making

### Q24: When would you choose EKS vs self-managed vs OpenShift?

**Answer:**
| Scenario | Choice | Reasoning |
|---|---|---|
| AWS-native, cloud-first, 5-person team | **EKS** | Least ops burden, IRSA/Karpenter, team too small for K8s ops |
| On-premises/air-gapped (no cloud) | **Self-managed (kubeadm/kubespray)** | Only option without cloud API |
| Banking/healthcare with FIPS/STIG compliance | **OpenShift** | Built-in compliance, SCC, Red Hat support SLA |
| Developer self-service platform for 50 teams | **OpenShift** | Web console, Projects, S2I, built-in pipelines |
| Cost-sensitive startup | **EKS + Karpenter + Spot** | $73/mo control plane, spot nodes, auto-consolidation |
| Multi-cloud (AWS + Azure) | **Self-managed or Rancher** | Portable, no cloud-specific dependencies |
| Telecom 5G/NFV workloads | **OpenShift** | CPU pinning, NUMA, SR-IOV, MachineConfig operator |

---

### Q25: Why Karpenter over Cluster Autoscaler?

**Answer:**
- **Context:** EKS cluster, variable workloads (batch jobs + steady web traffic), cost optimization needed.
- **Decision:** Karpenter — 60s provisioning vs 3-5 min, intelligent instance selection, auto-consolidation.
- **Trade-off:** More complex config (NodePool + NodeClass CRDs) vs CA's simpler single deployment.
- **When CA is better:** Non-EKS clusters (Karpenter is EKS-only currently), very simple/static workloads, or team unfamiliar with Karpenter CRDs.
- **Result:** 40% cost reduction from consolidation (removed underused nodes) + spot diversification.

---

### Q26: Why VPC CNI over Calico on EKS?

**Answer:**
- **Context:** App needs to communicate directly with RDS, ElastiCache (in VPC). Want Security Groups on pods.
- **VPC CNI chosen:** Pods get real VPC IPs → can apply SG rules directly on pod IP → RDS SG allows specific pod CIDR. No NAT needed.
- **Trade-off:** IP exhaustion risk. Fix: prefix delegation (110 pods/node), careful subnet sizing.
- **When Calico is better on EKS:** Need NetworkPolicy enforcement (VPC CNI alone doesn't enforce NetworkPolicies — need Calico addon for that). Or need > 110 pods/node.
- **Hybrid approach:** VPC CNI for networking + Calico addon for NetworkPolicy enforcement (our actual setup).

---

### Q27: Helm vs Kustomize for K8s application deployment?

**Answer:**
| | Helm | Kustomize |
|---|---|---|
| **Use when** | Complex apps, many configurable values, marketplace distribution | Simple overlays, team prefers plain YAML |
| **Template language** | Go templates (`{{ .Values.x }}`) | No templates — patches on base YAML |
| **PR readability** | Harder (reviewer must understand Go templates) | Easy (reviewer sees actual YAML) |
| **Multi-env** | values-dev.yaml, values-prod.yaml | overlays/dev/, overlays/prod/ |
| **Dependency management** | Built-in (Chart.yaml dependencies) | None |
| **Rollback** | `helm rollback release 3` (built-in history) | `git revert` (relies on GitOps) |

**Our choice:** Helm for the application chart (many configurable values across environments), Kustomize for simple infrastructure components (single values differ).

**Note:** This is different from our DevSecOps pipeline project where we used Kustomize only (single app, simple diffs). Different projects = different tools based on context.

---

### Q28: Managed DB (RDS) vs In-cluster DB (StatefulSet) on Kubernetes?

**Answer:**
- **Decision:** Managed RDS for production. Always.
- **Reasoning:**
  - RDS: Auto-failover (<30s), automated backups, point-in-time recovery, zero DBA needed for ops.
  - StatefulSet PostgreSQL: YOU handle failover (Patroni), YOU handle backups (CronJob → S3), YOU patch the DB OS, YOU handle storage growth.
- **When StatefulSet is OK:** Dev/test (cost saving), air-gapped (no managed service available), specific compliance requirement to control all data paths.
- **Our architecture:** App tier on K8s (stateless) → connects to RDS via VPC peering + ExternalSecret for credentials. Best of both worlds.

---

### Q29: OpenShift Routes vs Kubernetes Ingress?

**Answer:**
| | K8s Ingress | OpenShift Route |
|---|---|---|
| Controller required? | Yes — install Nginx/Traefik/ALB yourself | No — built-in Router (HAProxy) |
| TLS | cert-manager + ClusterIssuer (install) | Auto-provisioned by router |
| Traffic splitting | Annotations (controller-specific) | Built-in `alternateBackends` (native canary) |
| Wildcard support | Depends on controller | Built-in |
| API | `networking.k8s.io/v1` | `route.openshift.io/v1` |

**Key point for interview:** OpenShift Routes came BEFORE K8s Ingress existed. They're more feature-rich out of box. If you're on OpenShift, use Routes (native). If you're migrating TO standard K8s, convert Routes to Ingress.

---

### Q30: How do you choose between EKS Fargate vs Managed Node Groups?

**Answer:**
| | Fargate | Managed Node Group |
|---|---|---|
| Node management | Zero (serverless pods) | You manage node group config |
| Scaling | Instant (per-pod, no node warmup) | 30-60s (Karpenter) or 2-5min (CA) |
| Cost (at steady load) | Expensive (pay per pod vCPU/memory) | Cheaper (bin-pack multiple pods) |
| Cost (at variable load) | Cheaper (scale to zero) | Pay for idle nodes at night |
| DaemonSets | ❌ Not supported | ✅ Supported |
| GPU | ❌ Not supported | ✅ Supported |
| Best for | Batch jobs, isolated workloads, unpredictable traffic | Steady workloads, need DaemonSets/GPU |

**Our approach:** Managed node groups for steady web workloads (bin-packed, cost-effective) + Fargate for batch/cron jobs (scale-to-zero, no idle cost).

---

## Section 6: Behavioral & Leadership

### Q31: How did you help the team transition from self-managed K8s to EKS?

**Answer (STAR):**
- **Situation:** Team built kubeadm cluster 2 years ago. Spending 20% of time on K8s ops (etcd backup, node patching, upgrades). Wanted to focus on application development instead.
- **Task:** Migrate to EKS without disrupting running applications or team productivity.
- **Action:** Proposed phased approach. Phase 1: Terraform EKS module (I built it). Phase 2: Deploy staging apps on EKS alongside old cluster. Phase 3: Traffic shift to EKS (Route53 weighted). Phase 4: Decommission old cluster. Ran weekly knowledge-transfer sessions: "EKS differences" (IRSA, ALB Controller, node groups).
- **Result:** Migration completed in 6 weeks. Ops overhead dropped from 20% to 5% (no more etcd backups, no manual node patching). Team velocity improved — shipping features instead of fighting infrastructure.

---

### Q32: Tell me about a K8s production incident and how you handled it.

**Answer (STAR):**
- **Situation:** Friday 4 PM — Karpenter scaled down a node that was running a StatefulSet pod with a PVC in us-east-1a. New pod scheduled in us-east-1b but PVC was AZ-locked to 1a → Pod stuck in Pending.
- **Task:** Restore service immediately, then prevent recurrence.
- **Action:**
  1. Immediate: Manually scheduled pod to us-east-1a node (override Karpenter). Service restored in 2 min.
  2. Root cause: Karpenter's consolidation didn't consider PVC AZ binding.
  3. Fix: Added `topology.kubernetes.io/zone` requirement to NodePool — Karpenter only provisions in AZs where PVCs exist.
  4. Also added: `storageClassName` with `volumeBindingMode: WaitForFirstConsumer` — PVC binds to same AZ as pod.
- **Result:** Never happened again. Added this check to our "K8s production readiness" checklist.

**Learning:** Stateful workloads on K8s need AZ-aware scheduling. PVCs and pods must be in the same AZ. Karpenter doesn't know this by default.

---

### Q33: How did you handle disagreement about whether to adopt OpenShift vs EKS?

**Answer (STAR):**
- **Situation:** Telecom client wanted OpenShift ($50K+/year). AWS team advocated EKS ($876/year). Both had valid arguments.
- **Task:** Make a recommendation that considered ALL stakeholders (compliance team, developers, finance, operations).
- **Action:** Created decision matrix weighted by client's priorities:
  - Compliance (40%): OpenShift wins (FIPS, STIG built-in).
  - Developer UX (25%): OpenShift wins (console, S2I, built-in pipelines).
  - Cost (20%): EKS wins ($50K vs $876).
  - AWS integration (15%): EKS wins (IRSA, ALB).
  - **Weighted score:** OpenShift 78, EKS 62.
- **Result:** Client chose OpenShift. Compliance and developer experience were non-negotiable for them. Documented: "If compliance requirements change, revisit with EKS."

**Learning:** At 12 YOE, your job isn't to advocate for YOUR preference — it's to help the organization make the best decision for THEIR context.

---

### Q34: How do you stay current with Kubernetes changes across 3 platforms?

**Answer:**
- **K8s upstream:** Read release notes every quarter. Focus on: deprecated APIs, new features, security changes.
- **EKS:** AWS blogs + eksctl changelog. Watch for managed add-on updates, new Karpenter features.
- **OpenShift:** Red Hat errata + OCP release notes. Focus on: SCC changes, operator updates.
- **Hands-on:** Home lab with k3s (lightweight K8s) for testing new features. EKS sandbox cluster with AWS credits.
- **Community:** KubeCon recordings, CNCF Slack, LearnK8s newsletter, ThoughtWorks radar.
- **Certifications:** CKA (certified). Keeps me sharp on core concepts.

---

## Section 7: Future & Improvements

### Q35: What's on your K8s platform roadmap?

**Answer:**
| Priority | Improvement | Why |
|---|---|---|
| 1 | OpenTelemetry (replace separate metrics/logs/traces tools) | Unified observability standard, vendor-neutral |
| 2 | Cilium (replace Calico + VPC CNI) | eBPF-based, faster NetworkPolicy, built-in observability |
| 3 | Gateway API (replace Ingress) | More expressive routing, cross-namespace, native traffic splitting |
| 4 | Platform Engineering (Backstage) | Self-service for developers (create namespace, deploy app, view logs) |
| 5 | Policy-as-Code (Kyverno ClusterPolicy) | Enforce: resource limits required, non-root, approved registries only |
| 6 | eBPF runtime security (Tetragon/Falco) | Detect anomalous behavior inside pods without sidecar |
| 7 | Multi-cluster (Argo ApplicationSet) | Same app deployed across dev/staging/prod clusters consistently |

---

### Q36: What Kubernetes trends should engineers watch in 2025-2026?

**Answer:**
1. **Gateway API** — Replacing Ingress. More powerful routing, role-based (infra team manages GatewayClass, app team manages HTTPRoute).
2. **eBPF everywhere** — Cilium (CNI + observability + security without sidecars). Tetragon (runtime security).
3. **Karpenter going multi-cloud** — Currently EKS-only, expanding to other providers.
4. **Ambient mesh** — Istio without sidecars (ztunnel). Less overhead, simpler.
5. **Wasm (WebAssembly) workloads** — Spin/Wasmtime running on K8s for lightweight functions.
6. **AI/ML on K8s** — GPU scheduling, training operators, model serving (KServe).
7. **Platform Engineering** — Internal Developer Platforms (Backstage, Kratix) abstracting K8s complexity.

---

### Q37: What would make you switch from EKS to something else?

**Answer:**
- **Multi-cloud requirement:** If company needs to run same workload on AWS + Azure → self-managed K8s (portable) or Rancher.
- **Cost becomes prohibitive:** At 50+ clusters × $73/mo = $3,650/mo just for control planes. At that scale, self-managed with dedicated platform team might be cheaper.
- **EKS version lag unacceptable:** EKS releases K8s versions ~2 months after upstream. If we need a feature immediately, self-managed gives it faster.
- **GKE for AI/ML:** If ML workloads become primary, GKE's TPU support and ML-specific features might justify the switch.

---

## Bonus: Cross-Cutting Questions

### Q38: How do you handle K8s security across all three environments?

**Answer:**
| Control | How We Implement |
|---|---|
| Pod security | PSA `restricted` profile on all prod namespaces (EKS/kubeadm). SCC restricted-v2 (OpenShift) |
| Image policy | Kyverno: only allow images from approved registry prefix + must be signed |
| RBAC | Least privilege — per-namespace roles, no cluster-admin for developers |
| Network | Default-deny NetworkPolicy in every namespace. Explicit allow rules only |
| Secrets | Never in Git. External Secrets Operator syncs from Secrets Manager/Vault |
| Runtime | Falco detects anomalous behavior (exec into pod, unexpected network calls) |
| Audit | API audit logging → CloudWatch (EKS) / EFK (OpenShift/kubeadm) |
| Scanning | Trivy scans images in CI. Periodic scan of running images for new CVEs |

---

### Q39: What's the cost to run K8s in each environment (small production)?

**Answer:**
| Component | Self-Managed | EKS | OpenShift (ROSA) |
|---|---|---|---|
| Control plane | 3× m5.large = $210/mo | $73/mo (managed) | $73 + subscription |
| Worker nodes (3× m5.large) | $210/mo | $210/mo | $210/mo |
| Monitoring | Self-hosted (free, node resources) | Container Insights ($50) or free | Included |
| Logging | Self-hosted ES (dedicated node $70) | CloudWatch ($100/50GB) | Included |
| Red Hat subscription | N/A | N/A | ~$4,000/mo |
| **Total** | **~$500/mo** | **~$560/mo** | **~$4,500/mo** |

**Savings trick:** EKS + Karpenter + Spot instances for non-critical workloads = 60-70% savings on worker nodes.

---

### Q40: How do you handle K8s upgrades across all three?

**Answer:**
| Phase | Self-Managed | EKS | OpenShift |
|---|---|---|---|
| Preparation | Read release notes, check deprecated APIs, backup etcd | Same + check managed add-on compatibility | Same (operator-managed) |
| Control plane | `kubeadm upgrade apply v1.29.0` (risky, 10-30 min) | API call/click (AWS does it, zero-downtime) | OTA via ClusterVersion operator (automatic) |
| Worker nodes | Cordon → drain → upgrade kubelet → uncordon (per node, manual) | Update node group AMI → rolling replacement (automatic) | MachineConfigPool (automatic rolling) |
| Validation | `kubectl get nodes`, test DaemonSets, Ingress, HPA | Same | Same |
| Rollback | Difficult (kubeadm doesn't support downgrade) | Not supported for control plane | Automatic if health checks fail |

**Golden rule (all environments):** One minor version at a time. Test in staging first. PDBs protect app availability during drain.

---

*End of Q&A Bank — 40 questions covering all 7 dimensions*
