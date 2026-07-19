# 3-Tier Application Deployment on AWS with Terraform

## Project: Production-Grade Java Application on AWS 3-Tier Architecture

**Author:** Siddharth Patel  
**Role:** Staff/Principal DevOps & Cloud Engineer (12 YOE)  
**GitHub:** github.com/siddharthpatel1993  
**Technologies:** Terraform, AWS (VPC, ALB, ASG, RDS, WAF, CloudFront), Java/Spring Boot

---

## Table of Contents

1. What is Tiered Architecture?
2. 1-Tier Architecture (Simple)
3. 2-Tier Architecture (Client-Server)
4. 3-Tier Architecture (Production Standard)
5. Why 3-Tier for Production?
6. AWS Services Mapping to Tiers
7. Project Architecture Diagram
8. VPC and Network Design
9. Web Tier (ALB + WAF + CloudFront)
10. Application Tier (EC2 ASG / ECS Fargate)
11. Database Tier (RDS Aurora Multi-AZ)
12. Security Design
13. Auto Scaling Strategy
14. Terraform Implementation Guide
15. Monitoring and Observability
16. Cost Estimation
17. Key Design Decisions
18. Interview Talking Points

---

## 1. What is Tiered Architecture?

Tiered architecture means splitting your application into separate layers. Each layer has one job. They talk to each other but run independently.

**Think of it like a restaurant:**
- Customer (user) talks to the waiter (web tier)
- Waiter takes order to kitchen (app tier)
- Kitchen gets ingredients from storage (database tier)

If the kitchen is busy, the waiter still greets new customers. If storage is being restocked, the kitchen still prepares existing orders. Each tier works independently.

**Why separate tiers?**
- Security — database is never exposed to internet
- Scaling — scale each tier independently based on its load
- Maintenance — update app code without touching database
- Failure isolation — database crash doesn't kill web server

---

## 2. 1-Tier Architecture (Everything on One Machine)

```
┌─────────────────────────────┐
│       SINGLE SERVER          │
│                             │
│  Web Server (Apache/Nginx)  │
│  Application (Java/Python)  │
│  Database (MySQL/Postgres)  │
│                             │
│  IP: 54.23.45.67 (public)  │
└─────────────────────────────┘
```

**Real Example:** WordPress on a single EC2 instance — Apache + PHP + MySQL all on one machine.

**When to use:** Personal blog, dev/test, hobby projects.

**Problems:**
- One server = single point of failure (server dies = everything dies)
- Can't scale (database eating CPU affects web server)
- Security risk (database exposed to internet)
- No separation (updating app risks breaking database)

---

## 3. 2-Tier Architecture (Client-Server)

```
┌──────────────┐         ┌──────────────┐
│  WEB + APP   │────────▶│   DATABASE   │
│   SERVER     │         │   SERVER     │
│              │         │              │
│ Nginx + Java │         │    MySQL     │
│ (public)     │         │ (private)    │
└──────────────┘         └──────────────┘
```

**Real Example:** Spring Boot app on EC2 connecting to RDS MySQL in a private subnet.

**When to use:** Small applications, internal tools, <1000 users.

**Improvement over 1-tier:**
- Database is separate (can scale independently)
- Database in private subnet (not exposed to internet)
- Can upgrade app without touching DB

**Still has problems:**
- Web and app combined — can't scale them separately
- Single app server = still single point of failure
- No load balancing
- No caching layer

---

## 4. 3-Tier Architecture (Production Standard)

```
         INTERNET
            │
    ┌───────▼───────┐
    │   WEB TIER    │  ← Public subnet
    │  ALB + WAF    │  ← Load balancing + security
    │  CloudFront   │  ← CDN for static assets
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │   APP TIER    │  ← Private subnet
    │  EC2 ASG or   │  ← Auto-scaling group
    │  ECS Fargate  │  ← Multiple instances
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │   DATA TIER   │  ← Isolated subnet (no internet)
    │  RDS Aurora   │  ← Multi-AZ (automatic failover)
    │  ElastiCache  │  ← Redis for caching
    └───────────────┘
```

**Real Example:** Amazon.com, Netflix, any production app serving millions of users.

**Each tier explained simply:**

| Tier | Job | Analogy |
|------|-----|---------|
| Web Tier | Receive user requests, distribute traffic, block attacks | Hotel reception — greets guests, directs to rooms |
| App Tier | Run business logic, process data, make decisions | Hotel kitchen — prepares what was ordered |
| Data Tier | Store and retrieve data safely | Hotel vault — stores valuables securely |

---

## 5. Why 3-Tier for Production?

| Benefit | How |
|---------|-----|
| High Availability | ALB spans 3 AZs, RDS Multi-AZ auto-failover |
| Scalability | ASG adds/removes app servers based on load |
| Security | Database has zero internet access, WAF blocks attacks |
| Zero-downtime deploys | Rolling update via ASG — old serves while new starts |
| Cost optimization | Scale app tier during peak, scale down at night |
| Fault isolation | App crash doesn't kill DB, DB failover doesn't kill app |
| Compliance | Network tiers satisfy SOC2/PCI requirements |

---

## 6. AWS Services Mapping to Tiers

```
┌─────────────────────────────────────────────────────────────┐
│                        WEB TIER                              │
│                                                             │
│  CloudFront (CDN) → ALB (Load Balancer) → WAF (Firewall)  │
│  ACM (TLS Certs)    Route53 (DNS)                          │
│  Subnet: PUBLIC (has internet gateway route)                │
├─────────────────────────────────────────────────────────────┤
│                        APP TIER                              │
│                                                             │
│  EC2 Auto Scaling Group  OR  ECS Fargate Service           │
│  Launch Template (AMI, user-data)                           │
│  NAT Gateway (outbound-only internet for patches)           │
│  Subnet: PRIVATE (no inbound from internet)                 │
├─────────────────────────────────────────────────────────────┤
│                        DATA TIER                             │
│                                                             │
│  RDS Aurora (Multi-AZ, encrypted, automated backup)         │
│  ElastiCache Redis (session store, caching)                 │
│  Subnet: DATA/ISOLATED (no internet at all)                 │
│  Accessible ONLY from App Tier security group               │
└─────────────────────────────────────────────────────────────┘
```


---

## 7. Project Architecture Diagram

```
                         ┌─────────────┐
                         │  Route 53   │ (DNS: app.example.com)
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │ CloudFront  │ (CDN + DDoS protection)
                         └──────┬──────┘
                                │
                    ┌───────────▼───────────┐
                    │      AWS WAF          │ (SQL injection, XSS, rate limit)
                    └───────────┬───────────┘
                                │
          ┌─────────────────────▼─────────────────────┐
          │            APPLICATION LOAD BALANCER        │
          │         (Public Subnet — 3 AZs)            │
          │   HTTPS:443 → Target Group (port 8080)     │
          └──────┬──────────────┬──────────────┬──────┘
                 │              │              │
        ┌────────▼───┐  ┌──────▼────┐  ┌─────▼──────┐
        │  EC2 (AZ-a)│  │ EC2 (AZ-b)│  │ EC2 (AZ-c) │
        │  App Server │  │ App Server│  │ App Server  │
        │ Private Sub │  │Private Sub│  │ Private Sub │
        └────────┬───┘  └──────┬────┘  └─────┬──────┘
                 │              │              │
          ┌──────▼──────────────▼──────────────▼──────┐
          │           RDS AURORA CLUSTER                │
          │     Primary (AZ-a) + Replica (AZ-b)        │
          │         Data Subnet (Isolated)             │
          │    Encrypted + Automated Backups            │
          └────────────────────────────────────────────┘
```

**Traffic Flow (simple):**
1. User types app.example.com → Route53 resolves to CloudFront
2. CloudFront serves cached static files OR forwards to ALB
3. WAF inspects request — blocks if malicious
4. ALB picks healthiest EC2 instance (round-robin)
5. EC2 processes request, queries RDS Aurora
6. Response flows back: EC2 → ALB → CloudFront → User

---

## 8. VPC and Network Design

### What is VPC?
Virtual Private Cloud = your own private network inside AWS. Like your own office building where you control who enters which floor.

### CIDR Planning

```
VPC: 10.0.0.0/16 (65,536 IPs — room to grow)

Public Subnets (ALB, NAT Gateway):
  10.0.1.0/24  (AZ-a) — 256 IPs
  10.0.2.0/24  (AZ-b) — 256 IPs
  10.0.3.0/24  (AZ-c) — 256 IPs

Private Subnets (App Servers):
  10.0.11.0/24 (AZ-a) — 256 IPs
  10.0.12.0/24 (AZ-b) — 256 IPs
  10.0.13.0/24 (AZ-c) — 256 IPs

Data Subnets (RDS, ElastiCache):
  10.0.21.0/24 (AZ-a) — 256 IPs
  10.0.22.0/24 (AZ-b) — 256 IPs
  10.0.23.0/24 (AZ-c) — 256 IPs
```

### Routing

| Subnet Type | Route to Internet | Why |
|-------------|-------------------|-----|
| Public | Yes (Internet Gateway) | ALB needs to receive traffic from users |
| Private | Outbound only (NAT Gateway) | App servers need to download patches, not receive direct traffic |
| Data | No internet at all | Database should NEVER talk to internet |

### NAT Gateway
- One per AZ (for high availability)
- Allows private subnet → internet (outbound only)
- Example: EC2 in private subnet needs to `yum update` or pull Docker images
- If NAT in AZ-a dies, AZ-b and AZ-c still work

---

## 9. Web Tier (ALB + WAF + CloudFront)

### Application Load Balancer (ALB)

**What it does:** Distributes incoming traffic across multiple EC2 instances.

**Simple analogy:** Airport check-in counters. Instead of one counter handling all passengers (overloaded), traffic is spread across 10 counters evenly.

**Key configurations:**
- Listener: HTTPS:443 (TLS termination — decrypts SSL here, not on each EC2)
- Target Group: EC2 instances on port 8080
- Health Check: GET /health every 15 seconds — unhealthy instance gets no traffic
- Cross-zone: Distributes evenly across all AZs
- Sticky sessions: Disabled (stateless app — sessions in Redis)

**Why ALB not NLB?**
- ALB = Layer 7 (HTTP). Can route by path (/api → app, /static → S3)
- NLB = Layer 4 (TCP). For gRPC, gaming, extreme performance needs

### AWS WAF (Web Application Firewall)

**What it does:** Inspects every HTTP request and blocks malicious ones.

**Simple analogy:** Security guard at building entrance — checks ID, blocks suspicious people.

**Rules we apply:**
- Rate limiting: Max 2000 requests/5min per IP (blocks DDoS)
- SQL injection: Blocks `'; DROP TABLE users;--` type attacks
- XSS: Blocks `<script>alert('hacked')</script>` in inputs
- Geo-blocking: Block countries where we don't operate (optional)
- IP reputation: AWS managed list of known bad IPs

### CloudFront (CDN)

**What it does:** Caches static content (images, CSS, JS) at edge locations worldwide.

**Simple analogy:** Instead of everyone going to one warehouse (slow), copies are kept in local shops near each customer (fast).

**Benefits:**
- Latency: 20ms from edge vs 200ms from origin
- Cost: Reduces ALB traffic by 60-70% (cached responses)
- DDoS: Shield Standard included free — absorbs volumetric attacks
- HTTPS: Free ACM certificate, enforce HTTPS-only

---

## 10. Application Tier (EC2 Auto Scaling Group)

### What is ASG?

Auto Scaling Group = a set of EC2 instances that automatically grows or shrinks based on demand.

**Simple analogy:** A taxi company. During morning rush, they deploy 50 taxis. At 2 AM, only 5 taxis are out. They adjust based on demand.

### Launch Template

Defines what each EC2 instance looks like:
```
- AMI: Amazon Linux 2023 (pre-baked with Java 17 + app JAR)
- Instance type: m5.large (2 vCPU, 8GB RAM)
- Security Group: Allow 8080 from ALB SG only
- IAM Role: S3 read (for configs), CloudWatch (for metrics)
- User-data: Start application on boot
```

### Scaling Policies

| Policy | Trigger | Action |
|--------|---------|--------|
| Target Tracking | CPU > 60% average | Add instances |
| Target Tracking | CPU < 30% average | Remove instances |
| Scheduled | Every weekday 8:50 AM | Min = 6 (pre-scale for traffic) |
| Scheduled | Every day 10 PM | Min = 2 (save cost at night) |

### Capacity Settings
```
Minimum: 2 (always running — even at 3 AM)
Desired: 3 (normal traffic)
Maximum: 20 (handles 10x spike)
```

### Health Checks
- EC2 check: Is the instance running? (basic)
- ELB check: Is /health returning 200? (application-level)
- Grace period: 300 seconds (don't kill instance while app starts)

### Deployment Strategy (Zero Downtime)
- Rolling update: Replace 1 instance at a time
- New instance must pass health check before old one is killed
- If new instance fails → rollback (keep old running)


---

## 11. Database Tier (RDS Aurora Multi-AZ)

### What is RDS Aurora?

Managed relational database. AWS handles backups, patching, failover, replication. You just use it.

**Simple analogy:** Renting a furnished apartment vs building a house. Aurora = you move in and use it. Self-managed DB = you build walls, plumbing, electricity yourself.

### Why Aurora over regular RDS MySQL?
- 3-5x faster than standard MySQL
- 6 copies of data across 3 AZs automatically
- Failover in <30 seconds (vs 60-120s for standard RDS)
- Auto-scaling storage (10GB → 128TB, no manual resize)
- Up to 15 read replicas with <10ms lag

### Configuration
```
Engine: Aurora MySQL 8.0
Instance: db.r5.large (2 vCPU, 16GB RAM)
Multi-AZ: Yes (automatic failover)
Encryption: Yes (KMS managed key)
Backup: 7 days retention, automated daily
Storage: Auto-scales (starts 20GB)
```

### Endpoints
- **Writer endpoint:** app-db.cluster-abc123.us-east-1.rds.amazonaws.com (always points to primary)
- **Reader endpoint:** app-db.cluster-ro-abc123.us-east-1.rds.amazonaws.com (load-balanced across replicas)

App uses writer for INSERT/UPDATE, reader for SELECT queries → reduces primary load.

### Security
- Data subnet (no internet route at all)
- Security group: Allow port 3306 ONLY from App tier SG
- IAM authentication (no password in code)
- Encrypted at rest (KMS) + encrypted in transit (SSL)
- No public accessibility

### Failover (What happens when primary dies?)
1. Aurora detects primary failure
2. Promotes replica to primary (<30 seconds)
3. Writer endpoint DNS flips to new primary
4. Application reconnects automatically (retry logic)
5. No data loss (synchronous replication within cluster)

---

## 12. Security Design

### Security Group Chain (Micro-segmentation)

```
Internet → ALB-SG (port 443 from 0.0.0.0/0)
              ↓
           APP-SG (port 8080 from ALB-SG only)
              ↓
           DB-SG  (port 3306 from APP-SG only)
```

**Key principle:** Each tier only accepts traffic from the tier above it. Database NEVER sees internet traffic — even if ALB is compromised, attacker must also compromise app server to reach DB.

### IAM Roles (No hardcoded credentials)
- EC2 instances: Instance profile with S3 read + CloudWatch write
- RDS: IAM authentication (app generates temporary token, no password)
- CI/CD: OIDC federation (GitHub Actions → assume role, no access keys)

### Encryption
- At rest: EBS (AES-256), RDS (KMS CMK), S3 (SSE-KMS)
- In transit: TLS 1.2+ everywhere (ALB terminates, app→DB uses SSL)

### Network Security
- NACLs: Deny known bad IP ranges at subnet level
- VPC Flow Logs: Capture all traffic for forensics
- Private subnets: App servers never directly reachable from internet
- VPC Endpoints: S3, Secrets Manager accessed privately (no internet path)

---

## 13. Auto Scaling Strategy

### Horizontal vs Vertical Scaling

| Type | What | Example | When |
|------|------|---------|------|
| Vertical | Bigger instance | m5.large → m5.2xlarge | Quick fix, has ceiling |
| Horizontal | More instances | 3 instances → 10 instances | Production standard, no ceiling |

We use **horizontal scaling** (ASG adds more EC2s).

### Scaling Based on Custom Metrics

Besides CPU, we scale on:
- Request count per target (from ALB): If >1000 req/instance → add more
- Queue depth (if using SQS): If >100 messages pending → add consumers

### Scale-In Protection
- Cooldown: 300 seconds after scale-out before allowing scale-in
- Instance warmup: 120 seconds (new instance needs time to be ready)
- Scale-in: Remove 1 at a time (conservative) — never remove 50% at once
- Protect from scale-in: Long-running jobs protected until complete

---

## 14. Terraform Implementation Guide

### Module Structure

```
terraform/
├── modules/
│   ├── vpc/
│   │   ├── main.tf          (VPC, subnets, IGW, NAT, routes)
│   │   ├── variables.tf     (CIDR, AZs, tags)
│   │   └── outputs.tf       (vpc_id, subnet_ids)
│   ├── alb/
│   │   ├── main.tf          (ALB, listener, target group, WAF)
│   │   ├── variables.tf     (vpc_id, subnets, cert_arn)
│   │   └── outputs.tf       (alb_dns, target_group_arn)
│   ├── asg/
│   │   ├── main.tf          (Launch template, ASG, policies)
│   │   ├── variables.tf     (ami, instance_type, min/max)
│   │   └── outputs.tf       (asg_name)
│   ├── rds/
│   │   ├── main.tf          (Aurora cluster, instances, subnet group)
│   │   ├── variables.tf     (engine, instance_class, credentials)
│   │   └── outputs.tf       (writer_endpoint, reader_endpoint)
│   └── monitoring/
│       ├── main.tf          (CloudWatch alarms, dashboards, SNS)
│       ├── variables.tf
│       └── outputs.tf
├── environments/
│   ├── dev/
│   │   ├── main.tf          (calls modules with dev values)
│   │   ├── backend.tf       (S3 state: dev account)
│   │   └── terraform.tfvars (small instances, 1 replica)
│   ├── staging/
│   │   ├── main.tf
│   │   ├── backend.tf       (S3 state: staging account)
│   │   └── terraform.tfvars (prod-like but smaller)
│   └── prod/
│       ├── main.tf
│       ├── backend.tf       (S3 state: prod account)
│       └── terraform.tfvars (full size, 3 AZs, Multi-AZ RDS)
└── README.md
```

### Key Terraform Patterns Used

**1. Remote State (team-safe):**
```hcl
backend "s3" {
  bucket         = "company-terraform-state"
  key            = "prod/3-tier/terraform.tfstate"
  region         = "us-east-1"
  dynamodb_table = "terraform-locks"
  encrypt        = true
}
```

**2. Module Composition (VPC module):**
```hcl
module "vpc" {
  source = "../../modules/vpc"

  cidr_block         = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
  environment        = "prod"

  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnets = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
  data_subnets    = ["10.0.21.0/24", "10.0.22.0/24", "10.0.23.0/24"]
}
```

**3. ASG with Rolling Update:**
```hcl
resource "aws_autoscaling_group" "app" {
  min_size         = var.min_size
  max_size         = var.max_size
  desired_capacity = var.desired_size

  vpc_zone_identifier = var.private_subnet_ids
  target_group_arns   = [var.target_group_arn]
  health_check_type   = "ELB"

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 80
    }
  }
}
```

**4. RDS Aurora (encrypted, Multi-AZ):**
```hcl
resource "aws_rds_cluster" "main" {
  engine         = "aurora-mysql"
  engine_version = "8.0.mysql_aurora.3.04.0"

  master_username = "admin"
  master_password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.data.name
  vpc_security_group_ids = [aws_security_group.db.id]

  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn

  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"

  skip_final_snapshot = false
}
```

### Environment Differences

| Setting | Dev | Staging | Prod |
|---------|-----|---------|------|
| Instance type | t3.small | m5.large | m5.large |
| ASG min/max | 1/2 | 2/4 | 3/20 |
| RDS instance | db.t3.medium | db.r5.large | db.r5.large |
| Multi-AZ RDS | No | Yes | Yes |
| WAF | Disabled | Enabled | Enabled |
| Backup retention | 1 day | 3 days | 7 days |
| CloudFront | No | No | Yes |

---

## 15. Monitoring and Observability

### CloudWatch Alarms

| Alarm | Threshold | Action |
|-------|-----------|--------|
| ALB 5xx errors | >5% for 5 min | Page on-call (PagerDuty) |
| ASG CPU | >70% for 3 min | Scale out + alert |
| RDS CPU | >80% for 5 min | Alert (consider read replica) |
| RDS free storage | <10GB | Alert (expand) |
| ALB healthy hosts | <2 | Page on-call |
| RDS connections | >80% max | Alert |

### Dashboards
- ALB: Request count, latency P50/P99, 4xx/5xx rate
- ASG: Instance count, CPU, memory, health status
- RDS: Connections, read/write latency, replication lag, IOPS

---

## 16. Cost Estimation (Monthly — us-east-1)

| Component | Spec | Monthly Cost |
|-----------|------|--------------|
| ALB | Standard, 100GB processed | ~$25 |
| EC2 (3x m5.large on-demand) | 3 instances 24/7 | ~$210 |
| NAT Gateway (3x) | Per AZ + data | ~$100 |
| RDS Aurora (Multi-AZ) | db.r5.large + replica | ~$400 |
| CloudFront | 100GB transfer | ~$10 |
| WAF | Basic rules | ~$10 |
| S3 (state, logs) | Minimal | ~$5 |
| **TOTAL** | | **~$760/month** |

**With Savings Plans (1-year):** ~$500/month (35% savings on EC2 + RDS)

---

## 17. Key Design Decisions

| Decision | Why | Alternative Considered |
|----------|-----|----------------------|
| 3 AZs (not 2) | Survives full AZ failure with capacity to spare | 2 AZs = lose 50% capacity on failure |
| ALB (not NLB) | Need L7 routing, WAF, path-based rules | NLB for TCP/gRPC only |
| NAT per AZ | One NAT dies, other AZs unaffected | Single NAT = SPOF |
| Aurora (not RDS MySQL) | Faster failover, auto-storage, more replicas | Standard RDS for cost-sensitive |
| ASG (not ECS) | Team familiar with EC2, simpler debugging | ECS Fargate for container-native |
| Terraform modules | Reusable across environments, DRY | Flat files = duplication |
| Separate state per env | Blast radius — dev mistake can't corrupt prod state | Single state = dangerous |
| Instance refresh | Zero-downtime AMI updates via ASG native feature | Manual drain + replace |

---

## 18. Interview Talking Points

### 2-Minute Version
"Deployed a Java Spring Boot application on AWS 3-tier architecture with Terraform. VPC with public/private/data subnets across 3 AZs, ALB with WAF for security, EC2 Auto Scaling Group in private subnets scaling on CPU and request count, and Aurora Multi-AZ for the database in isolated subnets. Everything provisioned via Terraform modules — same code promotes through dev, staging, prod with different tfvars. Handles 5000 req/s, auto-scales 3→20 instances, RDS failover in <30 seconds."

### Common Follow-Up Questions

**Q: Why not ECS/EKS instead of EC2 ASG?**
A: Team was already familiar with EC2 and AMI-based deployments. ASG with instance refresh gives us rolling deploys. For new projects I'd use ECS Fargate — less ops overhead, better resource efficiency.

**Q: How do you handle database schema changes?**
A: Flyway migrations in CI/CD. Expand-and-contract pattern — add new column first (backward compatible), deploy new code, then drop old column later. Never breaking changes.

**Q: What if traffic spikes 10x suddenly?**
A: ASG target tracking reacts in ~2 minutes. For known events (sales, launches), we use scheduled scaling to pre-warm 30 minutes before. ALB handles connection queueing during scale-out.

**Q: How do you do zero-downtime deploys?**
A: New AMI → update launch template → trigger instance refresh → ASG replaces instances one by one, keeping 80% healthy at all times. New instance must pass ALB health check before old one is terminated.

**Q: How do you handle secrets (DB password)?**
A: Stored in AWS Secrets Manager. EC2 reads at boot via IAM role (no password in code, no environment variables baked in AMI). RDS also supports IAM authentication for zero-password approach.

---

## Summary

This project demonstrates understanding of:
- Network architecture (VPC, subnets, routing, NAT)
- Compute scaling (ASG, health checks, rolling updates)
- Database HA (Aurora Multi-AZ, failover, read replicas)
- Security layers (WAF, SG chaining, encryption, IAM)
- Infrastructure as Code (Terraform modules, state, environments)
- Cost awareness (right-sizing, savings plans, NAT optimization)
- Production readiness (monitoring, alerting, backups, DR)

This is the foundational project every DevOps/Cloud engineer at 12 YOE must be able to explain end-to-end with confidence.
