# Project 8: Multi-Region High Availability & Disaster Recovery

## Production-Grade Cross-Region Failover — "What If a Region Dies?"

**Author:** Siddharth Patel  
**Role:** Staff/Principal DevOps & Cloud Engineer (12 YOE)  
**Technologies:** AWS Route53, Aurora Global Database, S3 Cross-Region Replication, Terraform, CloudFront, Auto Scaling, AWS FIS (Fault Injection Simulator)

---

## Table of Contents

1. Problem Statement
2. Architecture Overview
3. RTO/RPO Design Decisions
4. Route53 Failover Routing
5. Aurora Global Database (Cross-Region)
6. S3 Cross-Region Replication (CRR)
7. Compute Layer (Multi-Region ASG)
8. DR Testing & Chaos Engineering
9. Terraform Implementation
10. Interview Talking Points

---

## 1. Problem Statement

**The question every senior-level interviewer asks:**

> "Your entire primary region (us-east-1) goes down. How fast do you recover, and how much data do you lose?"

If you can't answer with concrete numbers (RTO/RPO) and a tested architecture — you're not ready for 12 YOE.

**What we built:**
- Active-Passive architecture across us-east-1 (primary) and us-west-2 (DR)
- Route53 health-check-based automatic failover
- Aurora Global Database with <1 second replication lag
- S3 Cross-Region Replication for static assets and backups
- Terraform modules that deploy identical infrastructure in both regions
- Quarterly DR drills with measured RTO/RPO

**Business context:** E-commerce platform, 99.95% SLA, $2M+ revenue/hour. Region outage = $2M/hour lost + customer trust destroyed.

---

## 2. Architecture Overview

```
                         Internet
                            │
                    ┌───────▼───────┐
                    │   Route 53    │
                    │ (Failover     │
                    │  Routing)     │
                    └───┬───────┬───┘
                        │       │
            Primary     │       │     DR (Standby)
          (us-east-1)   │       │    (us-west-2)
                        ▼       ▼
               ┌─────────┐   ┌─────────┐
               │CloudFront│   │CloudFront│
               └────┬────┘   └────┬────┘
                    │              │
               ┌────▼────┐   ┌────▼────┐
               │   ALB   │   │   ALB   │
               └────┬────┘   └────┬────┘
                    │              │
               ┌────▼────┐   ┌────▼────┐
               │   ASG   │   │ ASG (0) │  ← Scaled to 0 normally
               │ (3 inst)│   │ min=0   │  ← Scales up on failover
               └────┬────┘   └────┬────┘
                    │              │
               ┌────▼────┐   ┌────▼────┐
               │  Aurora  │   │  Aurora  │
               │ Primary  │──▶│ Read     │  ← Async replication (<1s)
               │ Cluster  │   │ Replica  │  ← Promoted on failover
               └─────────┘   └─────────┘
                    │              │
               ┌────▼────┐   ┌────▼────┐
               │  S3     │──▶│  S3      │  ← Cross-Region Replication
               │(primary)│   │  (DR)    │
               └─────────┘   └─────────┘
```

**Design:** Active-Passive (Warm Standby)
- Primary region serves ALL traffic
- DR region has infra deployed but compute scaled to zero (or minimum)
- Failover is automatic via Route53 health checks
- DB replication is continuous (Aurora Global)
- Static data replicated via S3 CRR

---

## 3. RTO/RPO Design Decisions

### What is RPO and RTO? (Simple English)

**RPO (Recovery Point Objective) — "How much DATA can we LOSE?"**

Simple analogy: RPO is like asking "when did you last save your Word document?"
- If you save every 5 minutes → max you lose = 5 minutes of typing
- If you save every 1 hour → max you lose = 1 hour of typing

In our project: Aurora Global replicates every ~1 second. If the region dies RIGHT NOW, we lose maximum 1 second of data.

**RTO (Recovery Time Objective) — "How long are we DOWN?"**

Simple analogy: If your car breaks down, how quickly can you get a replacement?
- Spare car in driveway → 5 minutes (walk, get keys, drive)
- Need to rent a car → 2 hours (call, wait, paperwork)
- Need to buy a new car → days

In our project: Route53 detects failure in 30s, DNS switches in 60s, compute scales in 90s. Total: ~3 minutes.

**One Picture to Remember Both:**

```
         ← RPO (data loss) →          ← RTO (downtime) →
         
─────────────────────────── DISASTER ──────────────────────────── RECOVERED
                            EVENT
         
 Last good data              │                                First request
 was replicated              │                                served from DR
 1 second ago                │                                3 min later
                             │
                        💥 Region dies 💥
```

**Real Example from Our Platform:**
```
10:00:00.000 — Customer places order → saved to Aurora (us-east-1)
10:00:00.800 — Aurora replicates to us-west-2 (arrives)
10:00:01.000 — us-east-1 DIES completely

RPO impact: Lost 0.2 seconds of data (maybe 1 transaction)

10:00:01 — Region fails
10:00:31 — Route53 detects (3 health check failures × 10s)
10:01:31 — DNS failover complete (users get new IP)
10:03:10 — DR instances healthy, serving traffic

RTO impact: Users had errors for ~3 minutes
```

**Why Both Matter (Business Perspective):**

| Application Type | Acceptable RPO | Acceptable RTO | DR Cost |
|---|---|---|---|
| Personal blog | 24 hours (daily backup) | 1 day | $5/month |
| Internal tool | 1 hour | 4 hours | $50/month |
| **Our e-commerce ($2M/hour)** | **< 5 seconds** | **< 5 minutes** | **$400/month** |
| Stock trading platform | 0 (zero loss) | 0 (instant) | $10,000+/month |

**Key rule:** Tighter RPO/RTO = more expensive. Our Pilot Light ($400/mo) gives <5s RPO and <5 min RTO — best cost/recovery balance for our business.

---

### Our Targets vs Achieved

| Metric | Target | Achieved (in DR drill) | How |
|---|---|---|---|
| **RPO** | < 5 seconds | ~1 second | Aurora Global replication lag |
| **RTO** | < 5 minutes | ~3 minutes | Route53 TTL (60s) + ASG scale-up (90s) + health check (30s) |

### Why Active-Passive Over Active-Active?

| Factor | Active-Active | Active-Passive (Our Choice) |
|---|---|---|
| Cost | 2x (full infra in both regions) | ~1.3x (DR infra minimal until failover) |
| Complexity | High (data conflict resolution, session routing) | Medium (simple failover) |
| RPO | Near-zero | <5 seconds |
| RTO | Near-zero | <5 minutes |
| Best for | $10M+/hour revenue, zero tolerance | $2M/hour, 5-min acceptable |

**Decision rationale:** Active-Active adds write-conflict complexity (DynamoDB Global Tables or Aurora Multi-Master). For our use case, <5 minutes RTO is acceptable and saves 40% infra cost.

### RTO Breakdown

```
Region failure detected          : 0:00
Route53 health check fails (3x)  : 0:30  (10s interval × 3 failures)
Route53 DNS failover triggers    : 0:30
DNS propagation (TTL=60s)        : 1:30
DR ASG scales from 0 → 3 inst   : 3:00  (warm AMI, pre-pulled images)
ALB health check passes          : 3:30
First request served from DR     : 3:30
```

---

## 4. Route53 Failover Routing

### How It Works

Route53 continuously checks health of primary region. If unhealthy → automatically routes DNS to DR region.

```
Normal state:
  app.example.com → 52.x.x.x (us-east-1 ALB) [Primary, healthy ✅]
  app.example.com → 44.x.x.x (us-west-2 ALB) [Secondary, standby]

Failover state:
  app.example.com → 44.x.x.x (us-west-2 ALB) [Now active ✅]
  Primary marked unhealthy ❌ → no traffic
```

### Health Check Configuration

```hcl
resource "aws_route53_health_check" "primary" {
  fqdn              = "primary-alb.us-east-1.elb.amazonaws.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 10

  tags = { Name = "primary-region-health" }
}

resource "aws_route53_record" "primary" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "app.example.com"
  type    = "A"

  failover_routing_policy {
    type = "PRIMARY"
  }

  alias {
    name                   = aws_lb.primary.dns_name
    zone_id                = aws_lb.primary.zone_id
    evaluate_target_health = true
  }

  set_identifier  = "primary"
  health_check_id = aws_route53_health_check.primary.id
}

resource "aws_route53_record" "secondary" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "app.example.com"
  type    = "A"

  failover_routing_policy {
    type = "SECONDARY"
  }

  alias {
    name                   = aws_lb.dr.dns_name
    zone_id                = aws_lb.dr.zone_id
    evaluate_target_health = true
  }

  set_identifier = "secondary"
}
```

**Key settings:**
- `request_interval = 10` — check every 10 seconds
- `failure_threshold = 3` — 3 consecutive failures = unhealthy (30s detection)
- TTL on alias records = 60s (how fast clients get new IP)
- `evaluate_target_health = true` — Route53 also checks ALB target health

---

## 5. Aurora Global Database

### Why Aurora Global Over RDS Multi-AZ?

| Feature | RDS Multi-AZ | Aurora Global |
|---|---|---|
| Scope | Same region (AZ failover) | Cross-region |
| Replication | Synchronous (same region) | Async (<1s lag cross-region) |
| Failover | Same-region AZ failure | Entire region failure |
| Promotion time | 60-120 seconds | <60 seconds |
| Read in DR | ❌ No | ✅ Yes (read replica active) |

### Architecture

```
us-east-1 (Primary)              us-west-2 (DR)
┌─────────────────┐              ┌─────────────────┐
│ Aurora Cluster   │  ──async──▶ │ Aurora Cluster   │
│  Writer          │  (<1s lag)  │  Reader          │
│  + 2 Readers     │              │  (promote-able)  │
└─────────────────┘              └─────────────────┘
```

### Terraform

```hcl
# Primary cluster (us-east-1)
resource "aws_rds_global_cluster" "main" {
  global_cluster_identifier = "app-global-db"
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"
  database_name             = "appdb"
  storage_encrypted         = true
}

resource "aws_rds_cluster" "primary" {
  provider                  = aws.primary
  cluster_identifier        = "app-db-primary"
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"
  global_cluster_identifier = aws_rds_global_cluster.main.id
  master_username           = var.db_username
  master_password           = var.db_password
  backup_retention_period   = 35
  preferred_backup_window   = "03:00-04:00"
  storage_encrypted         = true
}

# DR cluster (us-west-2) — read replica, promote-able
resource "aws_rds_cluster" "dr" {
  provider                  = aws.dr
  cluster_identifier        = "app-db-dr"
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"
  global_cluster_identifier = aws_rds_global_cluster.main.id
  # No master_username/password — it's a replica
}
```

### Failover (Promotion) — During DR Event

```bash
# Remove DR cluster from global cluster (detaches and promotes)
aws rds remove-from-global-cluster \
  --global-cluster-identifier app-global-db \
  --db-cluster-identifier arn:aws:rds:us-west-2:123456789:cluster:app-db-dr \
  --region us-west-2

# DR cluster is now an independent writer — serving traffic
# RTO for DB: ~30-60 seconds
```

### Monitoring Replication Lag

```yaml
# CloudWatch alarm on replication lag
- MetricName: AuroraGlobalDBReplicationLag
  Threshold: 5000  # 5 seconds in milliseconds
  Action: SNS → PagerDuty (if lag > 5s, something is wrong)
```

---

## 6. S3 Cross-Region Replication (CRR)

### What Gets Replicated

| Bucket | Content | Why Replicate |
|---|---|---|
| `app-static-assets` | Images, CSS, JS | DR region needs to serve static content |
| `app-backups` | DB snapshots, configs | DR needs restore capability |
| `app-user-uploads` | User-generated content | Users expect their data in DR |

### Terraform

```hcl
resource "aws_s3_bucket" "primary" {
  provider = aws.primary
  bucket   = "app-static-assets-primary"

  versioning { enabled = true }  # Required for CRR
}

resource "aws_s3_bucket" "dr" {
  provider = aws.dr
  bucket   = "app-static-assets-dr"

  versioning { enabled = true }
}

resource "aws_s3_bucket_replication_configuration" "replication" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary.id
  role     = aws_iam_role.replication.arn

  rule {
    id     = "replicate-all"
    status = "Enabled"

    destination {
      bucket        = aws_s3_bucket.dr.arn
      storage_class = "STANDARD"
    }
  }
}
```

**Key point:** S3 CRR is eventually consistent (usually seconds, but no SLA). Not suitable as sole DB backup strategy — Aurora Global handles the data layer.

---

## 7. Compute Layer (Multi-Region ASG)

### Strategy: Warm Standby

- Primary: ASG min=3, max=10 (serving traffic)
- DR: ASG min=0, max=10 (no instances running, saves cost)
- On failover: CloudWatch alarm triggers ASG scaling policy → min=3

### Why min=0 in DR?

**Cost:** 3 × m5.large × 24/7 = ~$200/month wasted in DR if just sitting idle.
**Trade-off:** Extra 90 seconds on RTO (instance launch time) vs $200/month saved.
**Mitigation:** Use warm pools or pre-baked AMIs to reduce launch time.

### Terraform

```hcl
# DR ASG — scaled to 0, ready to scale up
resource "aws_autoscaling_group" "dr" {
  provider            = aws.dr
  name                = "app-asg-dr"
  min_size            = 0    # No instances normally
  max_size            = 10
  desired_capacity    = 0    # No instances normally
  vpc_zone_identifier = var.dr_private_subnets
  target_group_arns   = [aws_lb_target_group.dr.arn]

  launch_template {
    id      = aws_launch_template.dr.id
    version = "$Latest"
  }

  # Warm pool — instances in stopped state, faster launch
  warm_pool {
    pool_state                  = "Stopped"
    min_size                    = 2
    max_group_prepared_capacity = 4
  }
}

# CloudWatch alarm to trigger scale-up on failover
resource "aws_cloudwatch_metric_alarm" "dr_activate" {
  provider            = aws.dr
  alarm_name          = "dr-failover-activate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = 60
  statistic           = "Minimum"
  threshold           = 0  # 0 = unhealthy

  dimensions = {
    HealthCheckId = aws_route53_health_check.primary.id
  }

  alarm_actions = [aws_autoscaling_policy.dr_scaleup.arn]
}
```

---

## 8. DR Testing & Chaos Engineering

### DR Drill Schedule

| Drill Type | Frequency | What We Do |
|---|---|---|
| Tabletop exercise | Monthly | "What if us-east-1 goes down?" walkthrough with team |
| Partial failover | Quarterly | Fail one AZ, verify ALB routes around it |
| Full region failover | Semi-annually | Simulate full region outage, measure RTO/RPO |
| Chaos experiments | Ongoing | AWS FIS: kill instances, inject latency, fail DNS |

### Full Failover Drill Procedure

```
1. Announce drill (stakeholders notified)
2. Verify DR readiness:
   □ Aurora replication lag < 1s?
   □ S3 CRR status: healthy?
   □ DR AMI up-to-date?
   □ DR secrets/configs current?

3. Simulate failure:
   - Disable Route53 health check endpoint in primary
   - OR: Use AWS FIS to simulate region-level disruption

4. Measure:
   □ Time to detect (health check failure)  → TARGET: <30s
   □ Time to failover (DNS switches)        → TARGET: <90s
   □ Time to serve first request from DR    → TARGET: <5 min
   □ Data loss (compare last primary write vs first DR read) → TARGET: <5s

5. Verify DR functionality:
   □ Application login works?
   □ Read operations succeed?
   □ Write operations succeed (DB promoted)?
   □ External integrations reachable?

6. Failback:
   - Restore primary region
   - Re-establish Aurora Global replication
   - Route53 health check passes → traffic returns to primary
   - Verify data consistency

7. Post-drill report:
   - Actual RTO: ___
   - Actual RPO: ___
   - Issues found: ___
   - Action items: ___
```

### AWS Fault Injection Simulator (FIS) Experiments

```json
{
  "description": "Simulate primary region compute failure",
  "targets": {
    "ec2Instances": {
      "resourceType": "aws:ec2:instance",
      "resourceTags": { "Environment": "production", "Region": "primary" },
      "selectionMode": "ALL"
    }
  },
  "actions": {
    "stopInstances": {
      "actionId": "aws:ec2:stop-instances",
      "parameters": { "startInstancesAfterDuration": "PT30M" },
      "targets": { "Instances": "ec2Instances" }
    }
  },
  "stopConditions": [
    { "source": "aws:cloudwatch:alarm", "value": "arn:aws:cloudwatch:...:alarm:dr-error-rate-too-high" }
  ]
}
```

**Safety nets:**
- Stop condition: If DR error rate > 10%, abort experiment immediately
- Experiments run during low-traffic window (2 AM)
- All stakeholders notified before and after
- Rollback plan documented before experiment starts

### Last Drill Results (Example)

```
Date: 2026-Q1 Full Failover Drill
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Health check failure detected:    28 seconds ✅ (target: <30s)
DNS failover initiated:           31 seconds ✅
DR ASG scaled to 3 instances:     2 minutes 15 seconds ✅
First request served from DR:     3 minutes 10 seconds ✅ (target: <5 min)
Data loss measured:               0.8 seconds ✅ (target: <5s)

Issues found:
  - DR region missing 2 environment variables (config drift)
  - One Lambda function had hardcoded primary region endpoint
  
Action items:
  - [DONE] Add config drift detection (weekly Terraform plan in DR)
  - [DONE] Parameterize all region references in Lambda functions
```

---

## 9. Terraform Implementation

### Multi-Region Module Structure

```
terraform/
├── modules/
│   ├── vpc/              (identical VPC in both regions)
│   ├── compute/          (ALB + ASG + Launch Template)
│   ├── database/         (Aurora cluster)
│   ├── dns/              (Route53 failover records)
│   └── storage/          (S3 + CRR)
├── environments/
│   ├── production/
│   │   ├── main.tf       (calls modules for BOTH regions)
│   │   ├── primary.tf    (us-east-1 specific)
│   │   ├── dr.tf         (us-west-2 specific)
│   │   ├── global.tf     (Route53, Aurora Global, S3 CRR)
│   │   └── variables.tf
│   └── staging/
│       └── ...
└── providers.tf
```

### Provider Configuration

```hcl
provider "aws" {
  alias  = "primary"
  region = "us-east-1"
}

provider "aws" {
  alias  = "dr"
  region = "us-west-2"
}
```

### Key Design Principle: Same Module, Both Regions

```hcl
# Deploy identical VPC in both regions
module "vpc_primary" {
  source    = "../../modules/vpc"
  providers = { aws = aws.primary }
  
  cidr_block = "10.0.0.0/16"
  env        = "prod"
  region     = "us-east-1"
}

module "vpc_dr" {
  source    = "../../modules/vpc"
  providers = { aws = aws.dr }
  
  cidr_block = "10.1.0.0/16"  # Different CIDR for peering
  env        = "prod-dr"
  region     = "us-west-2"
}
```

**Why same module?** If primary and DR have different infra code, config drift happens. Same module = identical infrastructure guaranteed.

---

## 10. Interview Talking Points

### 2-Minute Version

"Built a multi-region active-passive DR architecture for an e-commerce platform. Primary region us-east-1 serves all traffic. Route53 health checks detect primary failure in 30 seconds and automatically failover DNS to us-west-2. Database layer uses Aurora Global Database with <1 second replication lag — RPO under 5 seconds. Compute layer in DR uses warm pools to launch in under 90 seconds. S3 Cross-Region Replication handles static assets. Total measured RTO in our last quarterly drill was 3 minutes 10 seconds. All infrastructure deployed via Terraform using identical modules for both regions to prevent config drift."

### Key Interview Q&A

**Q: "What's your RTO and RPO?"**  
A: RPO is ~1 second (Aurora Global async replication lag). RTO is ~3 minutes (30s detection + 60s DNS + 90s compute scale-up). We measure these in quarterly drills — not theoretical numbers, actual measured values.

**Q: "Why not active-active?"**  
A: Cost vs benefit. Active-active requires solving write conflicts (multi-master) and doubles infrastructure cost. For our $2M/hour revenue and 5-minute acceptable RTO, active-passive saves 40% infra cost while meeting SLA. If we were a $50M/hour trading platform with zero-second tolerance, active-active would be justified.

**Q: "How do you prevent config drift between regions?"**  
A: Same Terraform module deploys to both regions. Weekly `terraform plan` runs against DR region to detect drift. Any drift triggers a PagerDuty alert. Environment variables and secrets synced via AWS Secrets Manager with multi-region replication.

**Q: "What happens to in-flight requests during failover?"**  
A: Requests hitting primary during the 60s DNS TTL window will fail. Clients with stale DNS cache get errors for up to 60 seconds. Mitigation: CloudFront with origin failover (detects 5xx from primary origin → automatically tries DR origin) reduces this to <10 seconds for cached content.

**Q: "How do you test this?"**  
A: Four levels. Monthly tabletop exercises (discussion-based). Quarterly partial failover (kill one AZ). Semi-annual full region failover (measure actual RTO/RPO). Ongoing chaos experiments via AWS FIS (kill instances, inject latency). Every drill produces a report with measured metrics and action items.

**Q: "What was the hardest part?"**  
A: Database failover. Aurora Global promotion takes 30-60 seconds, and you lose the global cluster relationship. Failback after DR event requires re-creating the global cluster and re-syncing data. We automated this with a runbook + Ansible playbook, but it still takes 45 minutes for full failback. The second hardest: preventing config drift — Lambda functions with hardcoded region endpoints, environment variables missing in DR. Solved with weekly drift detection automation.

---

## Cost Summary

| Component | Primary Cost | DR Cost (standby) | DR Cost (active) |
|---|---|---|---|
| Compute (ASG) | 3 × m5.large = $200/mo | Warm pool (stopped) = $50/mo | Same as primary |
| Aurora | Writer + 2 readers = $800/mo | 1 reader (cross-region) = $300/mo | Promoted = $800/mo |
| ALB | $25/mo | $25/mo (idle) | $25/mo |
| S3 CRR | Source bucket cost | Replication = ~$20/mo | Same |
| Route53 | Health checks = $5/mo | Included | Included |
| **Total** | **~$1,030/mo** | **~$400/mo** | **~$1,030/mo** |

**DR overhead: ~39% of primary cost** for <5 minute RTO. Worth every penny when a region outage would cost $2M/hour in lost revenue.
