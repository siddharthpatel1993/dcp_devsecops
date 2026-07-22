# Project 7: Cloud Cost Optimization Platform (FinOps)

## Automated Cost Governance — Saving 35% ($180K/year)

**Author:** Siddharth Patel  
**Role:** Staff/Principal DevOps & Cloud Engineer (12 YOE)  
**Technologies:** AWS Cost Explorer, Lambda, EventBridge, CloudWatch, Terraform, Kubecost, Grafana

---

## Table of Contents

1. What is FinOps?
2. Why Cost Optimization Matters at 12 YOE
3. The Cost Problem (Before)
4. Architecture — What We Built
5. Automated Cost Controls
6. Kubernetes Cost Optimization
7. Cost Allocation & Chargeback
8. Savings Achieved (Numbers)
9. Governance (Preventing Waste)
10. Interview Talking Points

---

## 1. What is FinOps?

**FinOps = Financial Operations.** Making engineering teams responsible for their cloud costs — with visibility, accountability, and automation.

**Simple analogy:**
- Old way: One credit card for the whole company. Nobody knows who spent what. Bill shock at month-end.
- FinOps way: Each team has a budget. Real-time dashboard shows spending. Alerts at 80%. Auto-stops waste. Monthly review per team.

**Three pillars:**
1. **Inform** — Show teams what they're spending (visibility)
2. **Optimize** — Reduce waste (automation)
3. **Operate** — Governance (prevent waste before it happens)

---

## 2. Why Cost Optimization Matters at 12 YOE

At junior level: "I deployed the app." ✅  
At senior level: "I deployed the app AND it costs 40% less than the previous setup because I chose Graviton instances, spot for batch workloads, and GP3 over GP2." ✅✅✅

**Interviewers at senior level always ask:**
- "How do you manage cloud costs?"
- "Give me an example where you saved money"
- "How do you prevent cost overruns?"

If you can't answer with numbers, you look like someone who just spends company money without thinking.

---

## 3. The Cost Problem (Before) — Connected to Our Projects

### How Cost Was Wasting Money in Projects 1, 2, and 3

```
Monthly AWS bill: $45,000/month (growing 20% monthly)

WHERE THE MONEY WAS LEAKING:
```

### Project 2 (3-Tier AWS Architecture) — Cost Leaks

| Problem | What Was Happening | Monthly Waste |
|---|---|---|
| Oversized EC2 in ASG | m5.2xlarge running at 8% CPU (team picked "big just in case") | $180/instance × 6 = $1,080 |
| NAT Gateway data transfer | App servers downloading from S3 through NAT ($0.045/GB) instead of VPC Endpoint (free) | $800 |
| Dev/Staging RDS Multi-AZ | Why does DEV database need Multi-AZ failover? It doesn't. | $400 |
| ALB idle in dev | Dev ALB running 24/7, used 2 hours/day during testing | $25 |
| EBS GP2 instead of GP3 | Old default. GP3 is 20% cheaper AND faster | $150 |
| No S3 lifecycle | 2 years of ALB access logs sitting in S3 Standard ($0.023/GB) instead of Glacier ($0.004/GB) | $600 |
| CloudWatch logs forever | Retention set to "never expire" — accumulating cost | $200 |

**Total waste in 3-Tier project alone: ~$3,255/month**

### Project 3 (EKS/Kubernetes) — Cost Leaks

| Problem | What Was Happening | Monthly Waste |
|---|---|---|
| Over-provisioned pod requests | Devs set `cpu: "2", memory: "4Gi"` but actual usage: `cpu: 0.3, memory: 800Mi`. Nodes look full but are 80% idle. | $2,000 (extra nodes) |
| No spot for non-critical | CI runners and batch jobs on on-demand instances | $700 |
| Cluster Autoscaler slow | Keeps 2 extra nodes "just in case" (5-min provision buffer) | $280 |
| Staging EKS 24/7 | 3 worker nodes running all weekend for zero traffic | $400 |
| No Karpenter consolidation | 5 nodes at 30% utilization each — could be 2 nodes at 75% | $420 |
| Container Insights ($$$) | Paying CloudWatch for metrics Prometheus already collects free | $150 |

**Total waste in EKS project alone: ~$3,950/month**

### Project 1 (DevSecOps Pipeline) — Cost Leaks

| Problem | What Was Happening | Monthly Waste |
|---|---|---|
| Jenkins agent always running | t3.large agent 24/7 but builds only run 4 hours/day | $45 |
| SonarQube always on | Running 24/7 for 2 scans/day | $30 |
| S3 scan reports never cleaned | Trivy/ZAP HTML reports accumulating (no lifecycle) | $15 |
| Docker images never pruned in ECR | 200+ old images with no lifecycle policy | $10 |

**Total waste in CI/CD project: ~$100/month** (small, but multiplied across teams)

---

### The Bigger Picture: WHY It Was Happening

```
ROOT CAUSES (not just technical):

1. "Pick big instance, we might need it" → No rightsizing culture
2. "Leave it running, might need it later" → No auto-stop, no accountability
3. "Cloud is someone else's budget" → No per-team cost visibility
4. "I don't know how much my stuff costs" → No tagging, no dashboards
5. "Costs grew gradually — nobody noticed" → No alerts, no reviews
```

---

### After: How We Fixed Each Problem

### Project 2 (3-Tier) Optimizations

| Problem | Solution | Monthly Savings |
|---|---|---|
| Oversized EC2 | Compute Optimizer → switched to m5.large (matches real usage) | $720 |
| NAT data transfer | Added S3 VPC Endpoint (free, private path) | $800 |
| Dev RDS Multi-AZ | Terraform: `multi_az = var.environment == "prod" ? true : false` | $400 |
| GP2 → GP3 | Terraform module defaults to GP3 | $150 |
| S3 lifecycle | Auto-transition: 30d → IA, 90d → Glacier, 365d → delete | $600 |
| CloudWatch retention | Set all log groups to 30 days (not forever) | $200 |
| **Subtotal** | | **$2,870/mo saved** |

### Project 3 (EKS) Optimizations

| Problem | Solution | Monthly Savings |
|---|---|---|
| Over-provisioned pods | VPA in recommend mode → teams adjusted requests to actual usage | $2,000 |
| No spot for CI | Karpenter NodePool: `capacity-type: ["spot"]` for CI runners taint | $700 |
| Slow scaling | Switched to Karpenter (60s vs 3-5 min). Removed buffer nodes. | $280 |
| Staging 24/7 | EventBridge → Lambda scales node group to 0 at 8 PM weekdays + all weekend | $400 |
| Poor bin-packing | Karpenter `consolidationPolicy: WhenUnderutilized` — auto-removes half-empty nodes | $420 |
| Container Insights | Disabled. Already have Prometheus (free, same metrics). | $150 |
| **Subtotal** | | **$3,950/mo saved** |

### Project 1 (CI/CD) Optimizations

| Problem | Solution | Monthly Savings |
|---|---|---|
| Jenkins agent 24/7 | Kubernetes-based ephemeral agents (pod per build, dies after) | $45 |
| SonarQube 24/7 | Scheduled: scale to 0 outside work hours (or use SonarCloud) | $30 |
| S3 reports accumulating | S3 lifecycle: delete scan reports after 30 days | $15 |
| ECR images not pruned | ECR lifecycle policy: keep last 10 images per repo, delete older | $10 |
| **Subtotal** | | **$100/mo saved** |

---

### Before vs After Summary

```
BEFORE: $45,000/month (growing, uncontrolled, no visibility)

AFTER: $29,000/month (35% reduction)

HOW:
├── Project 2 savings: $2,870/month
├── Project 3 savings: $3,950/month  
├── Project 1 savings: $100/month
├── Non-prod auto-stop (ALL projects): $8,500/month
├── Savings Plans (steady baseline): $3,000/month
└── Other (orphans, lifecycle, Graviton): $2,480/month
    
TOTAL SAVINGS: ~$16,000/month = ~$192,000/year
```

---

### One Visual: How FinOps Wraps Around All Projects

```
┌─────────────────────────────────────────────────────────────────────┐
│  FinOps Layer (THIS PROJECT — wraps around everything)               │
│                                                                     │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐          │
│  │ Project 1     │  │ Project 2     │  │ Project 3     │          │
│  │ CI/CD Pipeline│  │ 3-Tier AWS    │  │ EKS Platform  │          │
│  │               │  │               │  │               │          │
│  │ Optimized:    │  │ Optimized:    │  │ Optimized:    │          │
│  │ • Ephemeral   │  │ • Rightsized  │  │ • VPA         │          │
│  │   agents      │  │ • VPC Endpoint│  │ • Karpenter   │          │
│  │ • ECR prune   │  │ • GP3 default │  │ • Spot nodes  │          │
│  │ • Report      │  │ • S3 lifecycle│  │ • Kubecost    │          │
│  │   lifecycle   │  │ • Dev auto-off│  │ • Auto-off    │          │
│  └───────────────┘  └───────────────┘  └───────────────┘          │
│                                                                     │
│  Controls:                                                          │
│  • Tagging SCP (Project 4) — can't create untagged resources       │
│  • Budget alerts per team/account                                   │
│  • Infracost on every Terraform PR (cost visible before merge)     │
│  • Monthly review meeting (team leads see their spend)             │
│  • Grafana cost dashboard (real-time per team per project)         │
│                                                                     │
│  Automation:                                                        │
│  • Auto-stop non-prod (Lambda + EventBridge — Project 5 pattern!)  │
│  • Auto-cleanup orphans (Lambda — same serverless approach)        │
│  • Auto-rightsize alerts (Compute Optimizer → Slack weekly)        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Key insight:** The FinOps automation uses the SAME serverless pattern as Project 5 (EventBridge → Lambda → notify). We already know how to build this.

---

## 4. Architecture — What We Built

```
┌─────────────────────────────────────────────────────────┐
│  AUTOMATED COST CONTROLS                                 │
│                                                          │
│  EventBridge (scheduler)                                 │
│       │                                                  │
│       ├── Every night 8 PM → Lambda: Stop non-prod      │
│       ├── Every morning 8 AM → Lambda: Start non-prod   │
│       ├── Every Monday → Lambda: Rightsizing report      │
│       ├── Every day → Lambda: Find idle resources        │
│       └── Budget alert → Lambda: Notify + auto-action   │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  VISIBILITY                                              │
│                                                          │
│  Cost Explorer API → Lambda → Grafana dashboard          │
│  Kubecost → Per-namespace K8s costs                      │
│  CUR (Cost & Usage Report) → Athena → QuickSight        │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  GOVERNANCE                                              │
│                                                          │
│  SCPs: Block expensive instances in sandbox              │
│  Tagging: SCP denies untagged resource creation          │
│  Budgets: Per-team alerts at 80%, 100%, 120%            │
│  Terraform: Enforce GP3, Graviton, spot in modules       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Automated Cost Controls

### 1. Auto-Stop Non-Production (Saves 65%)

**Problem:** Dev/staging instances run 24/7 but only used 9 AM - 7 PM weekdays.

**Solution:**
```
EventBridge Rule: cron(0 20 ? * MON-FRI *)  →  Lambda: stop_non_prod
EventBridge Rule: cron(0 8  ? * MON-FRI *)  →  Lambda: start_non_prod
```

**Lambda logic:**
```python
# Find all instances tagged Environment=dev or Environment=staging
instances = ec2.describe_instances(
    Filters=[{'Name': 'tag:Environment', 'Values': ['dev', 'staging']},
             {'Name': 'tag:AutoStop', 'Values': ['true']}]
)
# Stop them
ec2.stop_instances(InstanceIds=instance_ids)
# Also: stop RDS dev instances, scale ECS to 0, pause EKS node groups
```

**Savings:** 10 hours/weekday + 48 hours weekend = 118 hours saved out of 168 hours/week = **65% savings on non-prod compute.**

### 2. Idle Resource Cleanup

**Lambda runs daily — finds and reports:**

| Resource Type | Detection Rule | Action |
|---|---|---|
| Unattached EBS volumes | Status: available > 7 days | Snapshot → Delete (notify owner) |
| Unused Elastic IPs | Not associated to any instance | Release (notify owner) |
| Idle Load Balancers | 0 requests in 7 days | Notify owner → delete after 14 days |
| Old snapshots | Created > 90 days ago, no AMI reference | Delete |
| Stopped EC2 > 30 days | Stopped + tagged StopDate > 30 days old | Terminate (after notification) |

**Monthly cleanup savings:** ~$2,000/month (accumulated orphans)

### 3. Rightsizing Recommendations

```
Lambda (weekly) → Calls Compute Optimizer API → Generates report

Report example:
┌─────────────────────────────────────────────────────────────┐
│  Instance          Current        Recommended    Savings     │
│  app-server-1      m5.2xlarge     m5.large       $180/mo    │
│  worker-3          c5.xlarge      c5.large       $90/mo     │
│  jenkins           m5.xlarge      m5.large       $90/mo     │
│                                                              │
│  Total potential savings: $360/month                          │
└─────────────────────────────────────────────────────────────┘
```

Sent to Slack every Monday → team reviews → applies next sprint.

### 4. Savings Plans & Reserved Instances

| Strategy | Savings | Commitment | Best For |
|---|---|---|---|
| On-demand | 0% (baseline) | None | Short-term, unpredictable |
| Savings Plans (1-year) | 30-40% | 1 year | Steady compute (known minimum) |
| Savings Plans (3-year) | 50-60% | 3 years | Very stable workloads |
| Spot instances | 70-90% | None (can be interrupted) | Batch, CI/CD, fault-tolerant |
| Graviton (ARM) | 20% cheaper | None | Most workloads (just switch instance type) |

**Our approach:**
- Baseline (always running): Compute Savings Plans 1-year (covers 60% of compute)
- Burst (variable): On-demand (30% of compute)
- Batch/CI: Spot instances (10% of compute, 70% cheaper)
- All new: Graviton (m6g instead of m5 — 20% cheaper + faster)

---

## 6. Kubernetes Cost Optimization

### Kubecost (Per-Namespace Cost Visibility)

```
┌────────────────────────────────────────┐
│  Namespace        Monthly Cost   Waste │
│  app-prod         $1,200        5%     │
│  monitoring       $400          10%    │
│  app-staging      $600          65%    │  ← scale down!
│  ci-runners       $800          20%    │  ← use spot
│  data-pipeline    $300          0%     │
└────────────────────────────────────────┘
```

### K8s-Specific Optimizations

| Optimization | How | Savings |
|---|---|---|
| Right-size requests | VPA (Vertical Pod Autoscaler) recommends actual usage | 30-40% |
| Spot for non-critical | Karpenter NodePool with spot capacity-type | 70% on those nodes |
| Scale to zero | KEDA (scale on queue depth, 0 when empty) | 100% when idle |
| Bin-packing | Karpenter consolidation (fewer, fuller nodes) | 20-30% |
| Cluster auto-off | Non-prod EKS: scale node group to 0 evenings | 65% |

### Resource Requests — The Hidden Cost Problem

```
Team sets: requests: cpu: "2", memory: "4Gi"
Actual usage: cpu: "0.3", memory: "800Mi"

Result: Node capacity reserved but unused. Cluster looks full but is actually 80% idle.
```

**Fix:** VPA in recommend mode → shows actual usage → teams adjust requests → fewer nodes needed.

---

## 7. Cost Allocation & Chargeback

### Mandatory Tagging

```
Every resource MUST have:
- Team: payments / orders / platform / data
- Environment: prod / staging / dev / sandbox
- Service: order-api / payment-processor / dashboard
- CostCenter: CC-1234
```

**Enforcement:** SCP denies creation of untagged resources:
```json
{
  "Effect": "Deny",
  "Action": ["ec2:RunInstances", "rds:CreateDBInstance"],
  "Condition": {
    "Null": { "aws:RequestTag/Team": "true" }
  }
}
```

### Monthly Cost Review

```
Monthly report (automated → Slack + Email):

Team: Payments
├── Prod:    $3,200  (within budget ✅)
├── Staging: $800   (over budget ⚠️ — why so high?)
├── Dev:     $400   (within budget ✅)
└── Total:   $4,400  (budget: $5,000)

Action items:
- Staging: 3 idle RDS instances. Delete? (saves $600)
- Prod: Switch to Graviton. (saves $640)
```

---

## 8. Savings Achieved (Numbers)

| Optimization | Monthly Savings | Annual |
|---|---|---|
| Non-prod auto-stop (evenings/weekends) | $8,500 | $102,000 |
| Rightsizing (Compute Optimizer) | $2,200 | $26,400 |
| Savings Plans (1-year commit) | $3,000 | $36,000 |
| Idle resource cleanup | $1,500 | $18,000 |
| S3 lifecycle (Standard → IA → Glacier) | $800 | $9,600 |
| Graviton migration | $1,200 | $14,400 |
| Spot for CI/CD | $700 | $8,400 |
| **TOTAL** | **$17,900** | **$214,800** |

**Before:** $45,000/month  
**After:** $29,000/month  
**Savings:** 35% reduction, ~$180K+/year saved

---

## 9. Governance (Preventing Waste)

### Preventive Controls

| Control | How | Prevents |
|---|---|---|
| Mandatory tagging (SCP) | Can't create without tags | Unattributable cost |
| Instance type restriction (SCP) | Sandbox: only t3.small/medium | $10K GPU experiments in sandbox |
| Budget alarms | Alert at 80%, 100%, 120% | Surprise bills |
| Terraform modules enforce best practices | GP3 default, encryption, lifecycle | Developer choosing expensive defaults |
| PR review for infra changes | Infracost comment on PR | "This change adds $150/month" |

### Infracost (Cost in PR)

```
# Comment on every Terraform PR:

💰 Monthly cost will increase by $150
   
   + aws_nat_gateway.new    $32/month
   + aws_rds_cluster.new    $118/month
   
   Total monthly: $4,520 → $4,670
```

Developer sees cost BEFORE merging. Reviewer can ask: "Do we really need a NAT gateway here?"

---

## 10. Interview Talking Points

### 2-Minute Version

"Built an automated FinOps platform that reduced our AWS bill by 35%, saving $180K annually. Key levers: Lambda-based auto-stop for non-prod (saves 65% compute outside hours), Compute Optimizer-driven rightsizing reports weekly, mandatory tagging enforced via SCPs for cost attribution, S3 lifecycle policies moving 2 years of data to Glacier, and Savings Plans for the stable baseline. On Kubernetes, Kubecost provides per-namespace cost visibility with chargeback to teams. Infracost on every Terraform PR shows cost impact before merge. Made cost a team-level responsibility with monthly reviews and Grafana dashboards per team."

### Key Interview Q&A

**Q: "How do you reduce cloud costs?"**  
A: Three phases. (1) Visibility — tag everything, dashboard per team, Kubecost per namespace. Teams that see their spend reduce it 15% just from awareness. (2) Optimize — auto-stop non-prod, rightsize, Savings Plans, spot for batch, Graviton, S3 lifecycle. (3) Govern — SCPs prevent expensive resources, Infracost shows cost in PR, budgets alert at 80%.

**Q: "Give me a specific example of cost savings."**  
A: Non-prod auto-stop alone saved $102K/year. 10 dev instances + 5 staging instances running 24/7 but used only 10 hours/day on weekdays. Lambda stops them at 8 PM, starts at 8 AM. Weekends fully off. 65% compute savings with zero developer impact — they don't even notice.

**Q: "How do you handle cost vs reliability trade-offs?"**  
A: Never sacrifice production reliability for cost. Savings Plans on steady baseline (prod), on-demand for burst, spot ONLY for fault-tolerant (CI/CD, batch). Dev/staging get spot + auto-stop — it's OK if those are slower or interrupted. Prod gets on-demand + Multi-AZ + no auto-stop — reliability first. Cost optimization targets non-prod and waste, not production capacity.

**Q: "What about Kubernetes cost?"**  
A: Three problems unique to K8s. (1) Over-provisioned requests: VPA recommends actual usage, teams right-size. (2) Idle nodes: Karpenter consolidates underutilized nodes, terminates empty ones. (3) Non-prod clusters: Scale node groups to 0 evenings. Result: 40% K8s cost reduction without affecting any workload.
