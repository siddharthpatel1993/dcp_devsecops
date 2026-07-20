# Interview Q&A Bank: 3-Tier AWS Architecture with Terraform

## Project: Production-Grade Java Application on AWS — VPC, ALB, ASG, Aurora, WAF

**Technologies:** Terraform, AWS VPC, ALB, WAF, CloudFront, EC2 ASG, RDS Aurora, CloudWatch, Route53, S3, KMS, IAM

---

## Section 1: Project Story (STAR Format)

### Q1: Walk me through this project in 2 minutes.

**Answer:**
Designed and deployed a production-grade 3-tier architecture for a Java Spring Boot application on AWS using Terraform. VPC with 9 subnets across 3 AZs (public, private, data). Web tier: CloudFront + WAF + ALB with TLS termination. App tier: EC2 Auto Scaling Group in private subnets scaling between 3-20 instances based on CPU and request count. Data tier: Aurora MySQL Multi-AZ in isolated subnets with zero internet access, encrypted at rest and in transit. All infrastructure provisioned as Terraform modules — same code deploys to dev/staging/prod with different tfvars. Security group chaining ensures each tier only talks to adjacent tier. Handles 5000 req/s, auto-scales on demand, RDS failover in <30 seconds, and full DR via Pilot Light strategy with <5 min RTO.

**Follow-up they might ask:** "What was the traffic pattern and user count?"

---

### Q2: What was the business problem?

**Answer:**
- **Situation:** Java application running on 2 manually configured EC2 instances. No auto-scaling, no WAF, database on same instance, no IaC — everything ClickOps. Black Friday caused downtime (couldn't scale), and a security audit flagged public database access.
- **Task:** Redesign for production: high availability, auto-scaling, security compliance (SOC2), zero-downtime deployments, and everything as code for repeatability.
- **Action:** Designed 3-tier VPC architecture, implemented Terraform modules, security group chaining, WAF rules, ASG with scheduled + dynamic scaling, Aurora Multi-AZ with automatic failover, comprehensive CloudWatch monitoring.
- **Result:** Zero downtime since launch (6+ months), handled 10x traffic spike during campaign, passed SOC2 audit, reduced deployment risk with rolling updates, saved 35% cost with scheduled scaling (night scale-down).

---

### Q3: Why 3-tier over a simpler architecture?

**Answer:**
- **Context:** Production app, 5000+ req/s, payment data, SOC2 compliance, team of 8 engineers.
- **Options:** Single-tier (rejected: no HA, security risk), 2-tier (rejected: can't scale web/app independently), 3-tier (chosen), Kubernetes/ECS (considered but team not ready).
- **Decision:** 3-tier gives security isolation (DB never sees internet), independent scaling per tier, compliance satisfaction (network segmentation), and fault isolation.
- **Trade-off:** More complex than 2-tier. More AWS cost (NAT Gateways, ALB). But justified by availability requirements and security compliance.

---

### Q4: What was the most challenging part?

**Answer:**
Two things. First, **NAT Gateway high availability** — initially deployed single NAT Gateway (cost saving) but it became a single point of failure. When it had an issue, all private subnet outbound traffic died (app couldn't reach external APIs). Fixed by deploying one NAT per AZ (3 total). Cost went up $100/month but eliminated the SPOF.

Second, **Aurora failover testing** — the failover itself takes <30 seconds, but the application connection pool needed tuning. Default pool held dead connections to old primary for 60+ seconds. Fixed by configuring connection validation queries and shorter timeout + retry logic.

---

### Q5: What would you do differently?

**Answer:**
1. **ECS Fargate instead of EC2 ASG** — less operational overhead (no AMI patching, no instance management). Team was EC2-familiar at the time, but containers would be my choice today.
2. **Use AWS Secrets Manager from day one** — initially used Terraform variables for DB password (stored in state file). Moved to Secrets Manager later.
3. **Add VPC endpoints earlier** — S3 and Secrets Manager traffic went through NAT Gateway (costs money). VPC endpoints = private path, zero data transfer cost.
4. **Implement Infrastructure drift detection** — only added terraform plan drift checks after finding manual console changes in week 3.

---

### Q6: What was the measurable impact?

**Answer:**
| Metric | Before | After |
|---|---|---|
| Availability | ~99% (downtime during deploys) | 99.95% (zero-downtime rolling updates) |
| Scale capacity | Fixed 2 instances (manual) | 3-20 instances (automatic) |
| Security | DB publicly accessible | DB in isolated subnet, SG chain, WAF |
| Deploy time | 30 min (manual SSH + restart) | 5 min (AMI swap + instance refresh) |
| Disaster Recovery | None (rebuild manually) | Pilot Light: 5 min RTO, <1s RPO |
| Monthly cost | $600 (always 2x large instances) | $500 avg (right-sized + scheduled scaling) |
| IaC coverage | 0% (ClickOps) | 100% (Terraform modules) |

---

### Q7: What trade-offs did you make?

**Answer:**
| Trade-off | Chose | Gave Up | Why |
|---|---|---|---|
| EC2 ASG vs ECS Fargate | EC2 ASG | Container benefits | Team familiarity, faster delivery |
| 3 NAT Gateways vs 1 | 3 (one per AZ) | $100/mo saving | Eliminated SPOF |
| Aurora vs RDS MySQL | Aurora | Lower cost of standard RDS | Faster failover, auto-storage, more replicas |
| Pilot Light DR vs Active-Active | Pilot Light | Instant failover | Cost ($150/mo vs $760/mo) |
| CloudFront + WAF vs ALB only | CloudFront + WAF | Simpler setup | DDoS protection, caching, compliance |
| Terraform modules vs flat code | Modules | Simpler initial setup | Reusability across 3 environments |



---

## Section 2: Technical Deep-Dive (How It Works Under the Hood)

### Q8: Explain the VPC network design. Why 3 subnet tiers?

**Answer:**
```
VPC: 10.0.0.0/16 (65,536 IPs)
├── Public subnets (10.0.1-3.0/24): ALB, NAT Gateway → has Internet Gateway route
├── Private subnets (10.0.11-13.0/24): EC2 app servers → outbound via NAT only
└── Data subnets (10.0.21-23.0/24): RDS, ElastiCache → NO internet route at all
```
- **Public:** Only resources that MUST face internet (ALB receives traffic, NAT provides outbound).
- **Private:** App servers need outbound (patches, API calls) but should never be directly reachable. NAT provides one-way outbound.
- **Data:** Database has ZERO reason to touch internet. No NAT route. Only accessible from private subnet SG. This satisfies SOC2/PCI network segmentation.

**3 AZs each:** Survives entire AZ failure. With 2 AZs, losing one = 50% capacity gone. With 3 AZs, losing one = 67% capacity still available.

---

### Q9: How does Security Group chaining work?

**Answer:**
```
Internet → ALB-SG (port 443 from 0.0.0.0/0)
              ↓ (reference: source = ALB-SG)
           APP-SG (port 8080 from ALB-SG ONLY)
              ↓ (reference: source = APP-SG)
           DB-SG (port 3306 from APP-SG ONLY)
```
**Key:** SGs reference each other, not IP ranges. This means:
- Only ALB can reach app servers (not any IP in the VPC).
- Only app servers can reach the database (even a compromised bastion can't hit DB directly).
- If ALB is compromised, attacker still can't reach DB (must also compromise app server).

**Terraform:**
```hcl
resource "aws_security_group_rule" "app_from_alb" {
  type                     = "ingress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id  # Reference SG, not CIDR
  security_group_id        = aws_security_group.app.id
}
```

---

### Q10: How does ALB health check work and what happens when an instance fails?

**Answer:**
1. ALB sends `GET /health` to each target every 15 seconds.
2. Instance must return HTTP 200 within 5 seconds.
3. After 3 consecutive failures (45 seconds) → instance marked **unhealthy**.
4. ALB stops routing NEW requests to that instance.
5. Existing connections are allowed to drain (deregistration delay: 60s).
6. ASG detects unhealthy (ELB health check type) → terminates instance → launches replacement.
7. New instance boots → passes health check → ALB starts routing traffic to it.

**Total recovery time:** ~3 minutes (45s detection + 60s drain + 90s new instance boot + health check pass).

**Why ELB health check over EC2 health check?** EC2 health check only verifies the VM is running (OS alive). ELB health check verifies the APPLICATION is responding. App can be deadlocked with OS still running — ELB catch catches this, EC2 doesn't.

---

### Q11: Explain Aurora Multi-AZ failover in detail.

**Answer:**
1. Aurora stores 6 copies of data across 3 AZs (2 copies per AZ).
2. Primary instance handles all writes. Read replicas handle reads.
3. If primary fails → Aurora detects within 10 seconds.
4. Aurora promotes a read replica to new primary (< 30 seconds total).
5. **Writer endpoint DNS** (`cluster-abc.rds.amazonaws.com`) flips to new primary. No app code change needed.
6. Application reconnection: apps using writer endpoint reconnect automatically within a few seconds.

**Data loss:** Zero. Aurora uses synchronous replication within the cluster volume (all 6 copies consistent). Different from RDS Multi-AZ which uses synchronous block-level replication.

**Our configuration:** Primary in AZ-a, Replica in AZ-b. If AZ-a goes down completely, AZ-b replica becomes primary.

---

### Q12: How does Auto Scaling work with target tracking policy?

**Answer:**
```
Target: Average CPU = 60%

Current state: 3 instances, avg CPU = 80%
  → 80% > 60% target → ASG adds instances
  → Adds enough to bring average back to 60%
  → Formula: desired = current × (current_metric / target_metric) = 3 × (80/60) = 4 instances

After scale-out: 4 instances, avg CPU = 55%
  → 55% < 60% → no action (within tolerance)

Later: avg CPU drops to 25%
  → 25% < 60% → ASG removes instances (after cooldown period)
  → Removes one at a time, checks again after 300s cooldown
```

**Why target tracking over step scaling?** Simpler configuration (just set target), ASG calculates the math. Step scaling requires defining multiple thresholds and actions manually.

**We also use:**
- ALB RequestCountPerTarget (>1000 requests/instance → scale out even if CPU is low — I/O-bound app).
- Scheduled scaling: Min=6 at 8:50 AM (pre-warm before traffic), Min=2 at 10 PM (save cost at night).

---

### Q13: How does Terraform state management work for this project?

**Answer:**
```hcl
backend "s3" {
  bucket         = "company-terraform-state"
  key            = "prod/3-tier/terraform.tfstate"
  region         = "us-east-1"
  dynamodb_table = "terraform-locks"    # Prevents concurrent apply
  encrypt        = true                  # State encrypted at rest
}
```
- **S3 versioning:** Every `terraform apply` creates a new state version. Can restore previous state if corruption.
- **DynamoDB locking:** If engineer A runs `terraform apply`, engineer B's `apply` will fail with "state locked" error. Prevents state corruption from concurrent writes.
- **Separate state per environment:** `dev/`, `staging/`, `prod/` each have their own state file. A bug in dev Terraform can't affect prod state.
- **Sensitive data in state:** RDS password is in state file (unavoidable). That's why encryption + strict IAM access control on the S3 bucket is critical.

---

### Q14: What does the Terraform module structure look like and why?

**Answer:**
```
modules/           ← Reusable building blocks
  vpc/             ← Network: subnets, routes, NAT, IGW
  alb/             ← Load balancer + target group + WAF
  asg/             ← Launch template + ASG + scaling policies
  rds/             ← Aurora cluster + instances + subnet group
  monitoring/      ← CloudWatch alarms + dashboards + SNS

environments/      ← Environment-specific configuration
  dev/terraform.tfvars    ← t3.small, 1 instance, no WAF
  staging/terraform.tfvars ← m5.large, 2 instances, WAF enabled
  prod/terraform.tfvars    ← m5.large, 3-20 instances, full stack
```

**Why modules?**
1. **DRY:** VPC module written once, used in dev/staging/prod with different CIDRs.
2. **Blast radius:** Each module has clear inputs/outputs. Change in RDS module can't accidentally break VPC.
3. **Testing:** Can test a module in isolation (dev) before promoting to prod.
4. **Team scalability:** Network team owns VPC module, app team owns ASG module.

---

### Q15: How do you handle zero-downtime deployments with ASG?

**Answer:**
1. Build new AMI with updated application code (Packer or CI/CD).
2. Update Launch Template with new AMI ID.
3. Trigger ASG Instance Refresh:
   ```
   min_healthy_percentage: 80%
   instance_warmup: 120 seconds
   ```
4. ASG launches 1 new instance with new AMI.
5. New instance passes ALB health check (GET /health → 200).
6. ASG terminates 1 old instance.
7. Repeat until all instances are on new AMI.
8. At ALL times, 80%+ instances are healthy and serving traffic.

**Rollback:** If new instances keep failing health checks → instance refresh automatically aborts. Old instances remain. Change Launch Template back to previous AMI.

---

### Q16: How does WAF protect the application?

**Answer:**
WAF rules evaluated in order. First match wins.

| Priority | Rule | Action | What it catches |
|---|---|---|---|
| 1 | Rate limit (2000 req/5min/IP) | Block | DDoS, brute force |
| 2 | AWS Managed Rule: SQLi | Block | `'; DROP TABLE users;--` |
| 3 | AWS Managed Rule: XSS | Block | `<script>alert('xss')</script>` |
| 4 | IP Reputation List | Block | Known malicious IPs |
| 5 | Geo-restriction (optional) | Block | Countries where we don't operate |
| 6 | Default | Allow | Legitimate traffic passes |

**WAF attached to:** ALB (not CloudFront, because we want to inspect after CDN cache miss). All requests hitting origin pass through WAF.

**Metrics:** `BlockedRequests` metric in CloudWatch → alarm if >1000 blocked/min (unusual = possible attack).

---

### Q17: How does CloudFront integrate with ALB?

**Answer:**
```
User → CloudFront edge (150+ global locations)
  ├── Cache HIT: Response from edge (20ms latency)  ← 60-70% of requests
  └── Cache MISS: Forward to ALB origin (200ms) → cache response for next time
```

**Configuration:**
- Origin: ALB DNS name (not IP — ALB IP changes).
- Behavior: `/static/*` → cache 24 hours. `/api/*` → no cache (dynamic).
- TLS: ACM certificate on CloudFront (free). Viewer → CloudFront = HTTPS. CloudFront → ALB = HTTPS.
- Custom headers: CloudFront adds `X-Origin-Verify: secret-token`. ALB only accepts requests with this header → prevents bypassing CloudFront directly to ALB.

**Benefits:** 60-70% cache hit ratio reduces ALB traffic by that much. DDoS absorbed at edge (Shield Standard included free). Global latency improvement for static assets.

---

### Q18: What CloudWatch alarms do you have and what happens when they fire?

**Answer:**
| Alarm | Threshold | Severity | Action |
|---|---|---|---|
| ALB 5xx rate | >5% for 5 min | P1 | PagerDuty page → on-call wakes up |
| ALB latency P99 | >2s for 5 min | P2 | Slack alert → team investigates |
| ASG healthy hosts | <2 | P1 | PagerDuty + auto-scale |
| RDS CPU | >80% for 5 min | P2 | Consider adding read replica |
| RDS connections | >80% of max | P2 | App connection pool issue |
| RDS replication lag | >5 seconds | P2 | Investigate write volume |
| RDS free storage | <10GB | P2 | Aurora auto-expands, but alert anyway |
| NAT Gateway errors | >0 for 5 min | P2 | Outbound from private subnet broken |

**Routing path:** CloudWatch Alarm → SNS Topic → Lambda → routes to PagerDuty (P1) or Slack (P2) or Jira (P3).



---

## Section 3: Troubleshooting Scenarios

### Q19: ALB is returning 502 Bad Gateway to users. Walk me through debugging.

**Answer:**
1. **502 means:** ALB couldn't get a valid response from backend (EC2 targets).
2. **Check target group health:** AWS Console → Target Groups → are targets healthy?
   - All unhealthy → app crashed on all instances. Check instance logs.
   - Some unhealthy → partial failure. ALB should route around them.
3. **Check EC2 instances:** SSH (via SSM) → is app process running? `systemctl status app` → check if Java process is alive.
4. **Common causes:**
   - App crashed (OOM killed) → check `dmesg` and CloudWatch memory metric.
   - App started but listening on wrong port (target group expects 8080, app on 8000).
   - Security group: app SG doesn't allow inbound from ALB SG.
   - App responding but too slowly (ALB timeout = 60s, app takes 90s → 502).
5. **Fix:** Restart app / fix config / increase ALB timeout / increase instance size if OOM.

---

### Q20: Autoscaling triggered but new instances keep failing health checks. What's wrong?

**Answer:**
1. **Check health check configuration:** Is `/health` endpoint correct? Does app take longer than grace period (300s) to start?
2. **Connect to new instance (SSM):** Is the app running? Check `/var/log/cloud-init.log` — did user-data script fail?
3. **Common causes:**
   - AMI is stale — new AMI missing a dependency or config change.
   - Instance can't reach Secrets Manager/S3 (needs NAT Gateway or VPC endpoint — missing route).
   - Security group doesn't allow ALB → 8080 (SG attached to new instance wrong).
   - App starts but crashes immediately (missing env var, can't connect to DB).
4. **Debugging steps:** Launch instance manually from same launch template → SSM session → check app logs → identify root cause.
5. **Impact:** ASG keeps launching and killing instances (loop). Set `max_instance_lifetime` or `health_check_grace_period` longer to give time for debugging.

---

### Q21: RDS Aurora primary fails over. Application gets connection errors for 2 minutes. Why?

**Answer:**
1. **Aurora failover is <30 seconds.** But application connection pool holds stale connections to OLD primary.
2. **Root cause:** Connection pool (HikariCP/c3p0) cached connections. After DNS flips, old connections are to dead host.
3. **Fix:**
   - Set connection validation: `validationQuery=SELECT 1` with `testOnBorrow=true`.
   - Set max connection lifetime: 600 seconds (connections recycled, pick up new DNS).
   - Set connection timeout: 5 seconds (fail fast, don't hang on dead connection).
   - Use Aurora writer endpoint (DNS-based, flips automatically) — never hardcode IP.
   - Enable retry logic in app: on connection failure → wait 5s → retry (failover completes within 30s).
4. **After fix:** Application reconnects within 5-10 seconds of failover. Customers see ~5s blip, not 2 minutes.

---

### Q22: Monthly AWS bill spiked $500 unexpectedly. How do you investigate?

**Answer:**
1. **Cost Explorer:** Filter by service → which service increased? (NAT Gateway data transfer? RDS? EC2?)
2. **Common surprises:**
   - **NAT Gateway data transfer:** Private subnet pulling large objects from S3 through NAT ($0.045/GB). Fix: S3 VPC Endpoint (free).
   - **ASG max instances:** Scaling policy too aggressive → scaled to 20 instances during traffic spike → didn't scale down (cooldown too long). Fix: review alarm thresholds.
   - **Untagged resources:** Someone launched instances outside Terraform (no tags → hard to attribute).
   - **RDS storage:** Aurora auto-expanded (not charged per provisioned, charged per used GB — but snapshots accumulate).
3. **Prevention:**
   - AWS Budgets: alert at $700 (80% of expected $760).
   - Cost anomaly detection (AWS built-in).
   - Tag policy enforcement: all resources must have `Team`, `Environment` tags.
   - Monthly cost review meeting.

---

### Q23: VPC Flow Logs show rejected traffic from app tier to data tier. App can't reach database.

**Answer:**
1. **Check Security Groups:** Does DB-SG allow inbound 3306 from APP-SG?
   - Common mistake: SG rule references APP-SG by ID, but EC2 is in a DIFFERENT SG.
2. **Check NACLs:** NACLs are stateless. If inbound 3306 is allowed, is outbound ephemeral port (1024-65535) also allowed for responses?
3. **Check routing:** Does private subnet route table have route to data subnet? (Within same VPC, all subnets can reach each other by default — unless NACL blocks it.)
4. **Check RDS subnet group:** Is RDS deployed in the data subnets we think? Check RDS → Connectivity → Subnet group.
5. **Check DNS resolution:** Is the app using the Aurora writer endpoint (DNS)? Is VPC DNS resolution enabled?

**Most common cause at 12 YOE level:** Security group rule referencing wrong SG ID after a Terraform refactor (old SG destroyed, new one created with different ID, app SG still references old).

---

### Q24: Deploy went out (new AMI) but users report intermittent errors during instance refresh. What's happening?

**Answer:**
1. **Instance refresh behavior:** Rolling replacement — terminates old, launches new.
2. **Problem:** New instance boots → app starts → health check runs → but app isn't fully warm yet (loading caches, JIT compilation, DB connection pool warming).
3. **Result:** First 30-60 seconds of requests to new instance are slow/erroring.
4. **Fixes:**
   - Increase `instance_warmup` in instance refresh (120s → 180s).
   - Add startup script that pre-warms: hit /health multiple times, populate caches.
   - ALB health check `interval=10, unhealthyThreshold=3` — don't send traffic until 3 consecutive passes.
   - readiness check: custom health endpoint returns 200 only AFTER warmup complete.
5. **Key insight:** Health check passing ≠ ready for production traffic. Two-phase startup: healthy (process running) → ready (warmed up, can serve).

---

### Q25: CloudFront returns stale content after deployment. Users see old version of the app.

**Answer:**
1. **Cause:** CloudFront caches responses based on TTL. After deploying new version, edge cache still has old version until TTL expires.
2. **Fixes:**
   - **Cache invalidation:** `aws cloudfront create-invalidation --distribution-id X --paths "/*"` — forces CloudFront to fetch fresh from origin. Add this to deployment pipeline.
   - **Cache busting:** Static assets served with hash in filename (`app.abc123.js`). New deploy = new hash = different URL = no stale cache.
   - **Short TTL for dynamic:** `/api/*` behavior → cache TTL = 0 (no cache). Only static assets cached.
3. **Best practice:** Cache busting for static assets (no invalidation needed) + invalidation for HTML pages (index.html changes but same URL).
4. **Cost note:** First 1000 invalidation paths/month are free. After that, $0.005/path.

---

### Q26: Terraform plan shows "13 resources will be destroyed" when you only changed a variable. Why?

**Answer:**
1. **Likely cause:** Changed something that forces resource recreation (not in-place update).
2. **Common triggers:**
   - Changed `cidr_block` on a subnet → subnet must be destroyed and recreated (cascade destroys everything in it).
   - Changed `engine_version` on RDS → forces replacement (some versions aren't in-place upgradable).
   - Changed `name` attribute → many AWS resources can't be renamed → destroy + create.
   - Changed `availability_zones` on ASG → recreates ASG.
3. **Before applying:** Read the plan carefully. `# forces replacement` shows which attribute caused it.
4. **Prevention:**
   - Use `lifecycle { prevent_destroy = true }` on critical resources (RDS, VPC).
   - Test changes in dev first (same module, different tfvars).
   - Never change subnet CIDRs or AZs in production without a migration plan.
5. **If you need the change:** Plan a maintenance window, take snapshot, apply.



---

## Section 4: System Design (Architecture-Level Thinking)

### Q27: Design a 3-tier architecture for a company that handles 50,000 requests/second with PCI compliance.

**Answer:**

**Clarify:** Payment data, PCI-DSS Level 1, multi-region requirement, 99.99% SLA.

**Architecture changes from our standard:**
1. **Network:** Dedicated VPC for cardholder data environment (CDE). Separate from non-payment workloads. Transit Gateway connecting CDE VPC ↔ app VPC.
2. **WAF:** More aggressive rules — custom rules for card number patterns in responses (data loss prevention).
3. **Encryption:** KMS CMK with annual rotation. TLS 1.3 enforced (not 1.2). No wildcard certs.
4. **Database:** Aurora with IAM auth (no passwords), encrypted connections mandatory, audit logging to CloudTrail.
5. **Compute:** Dedicated hosts (not shared tenancy) — PCI requirement for some interpretations.
6. **Scaling:** Pre-provisioned capacity (50K req/s needs ~50 instances). HPA + predictive scaling. No scale-to-zero.
7. **Logging:** All access logs retained 1 year. Tamper-proof (S3 Object Lock). Real-time log analysis for anomalies.
8. **Multi-region:** Active-Active with Aurora Global Database and Route53 latency-based routing.

**Key PCI controls addressed:**
- Requirement 1: Firewall (SG chaining + WAF + NACLs)
- Requirement 3: Protect stored data (KMS encryption at rest)
- Requirement 4: Encrypt transmission (TLS everywhere)
- Requirement 10: Track all access (CloudTrail + VPC Flow Logs)

---

### Q28: The current architecture handles 5000 req/s. What changes for 100,000 req/s?

**Answer:**

**Bottleneck analysis at 10x:**

| Component | At 5K req/s | At 100K req/s | Change Needed |
|---|---|---|---|
| CloudFront | Handles any scale | Still fine (no change) | None |
| ALB | ~5000 new connections/s | Need multiple ALBs or NLB | Add NLB in front of ALBs, or use Route53 weighted |
| EC2 (m5.large) | 3-20 instances | 60-200 instances → ASG limit | Use c6g.2xlarge (compute-optimized), consider ECS/Fargate |
| Aurora | 1 writer handles ~10K req/s | Writer bottleneck | Add read replicas (15 max), CQRS pattern, caching |
| ElastiCache | Not used | MUST add | Redis cluster for session + hot data (reduce DB hits 80%) |

**Architecture evolution:**
1. Add ElastiCache Redis (most reads never hit Aurora).
2. CQRS: Write to Aurora, read from Redis/replicas.
3. Move to ECS/EKS (faster scaling than EC2 AMI launch).
4. API Gateway + Lambda for stateless endpoints (auto-scales instantly).
5. SQS for async processing (order placement → queue → processor).

---

### Q29: How would you migrate this application from EC2 ASG to ECS Fargate without downtime?

**Answer:**

**Strategy:** Parallel run with traffic shifting.

1. **Phase 1 — Build:** Containerize app (Dockerfile), create ECS task definition + service + target group.
2. **Phase 2 — Deploy alongside:** Register ECS target group with SAME ALB listener. ALB now has 2 target groups.
3. **Phase 3 — Weighted routing:** ALB listener rule: 90% → EC2 TG, 10% → ECS TG. Monitor.
4. **Phase 4 — Shift traffic:** 50/50, then 90% ECS, 10% EC2. Verify metrics.
5. **Phase 5 — Cutover:** 100% ECS. Keep EC2 as fallback for 1 week.
6. **Phase 6 — Decommission:** Remove EC2 ASG + Launch Template.

**Zero-downtime guarantee:** At every step, both target groups are serving. Shift is at ALB level (instant, no DNS propagation delay).

**Rollback at any step:** Change ALB weight back to 100% EC2.

---

### Q30: Design the monitoring and alerting strategy for this architecture from scratch.

**Answer:**

**Three-tier monitoring (matching three-tier architecture):**

```
Web Tier Monitoring:
  ├── Request rate, error rate (4xx/5xx), latency P50/P99
  ├── WAF blocked count, top blocked rules
  ├── CloudFront cache hit ratio, origin latency
  └── Certificate expiry (< 14 days = alert)

App Tier Monitoring:
  ├── Instance count (desired vs running), CPU, memory
  ├── Health check pass/fail, instance refresh progress
  ├── Application: JVM heap, GC pauses, thread count
  └── Custom business metrics: orders/min, payment success rate

Data Tier Monitoring:
  ├── Connections (active/max), CPU, IOPS
  ├── Replication lag, failover events
  ├── Slow queries (>1s), deadlocks
  └── Storage growth trend, backup success
```

**Alert routing:**
- P1 (page): User-facing impact confirmed → PagerDuty → on-call
- P2 (urgent): Degradation detected, not yet impacting → Slack #alerts → 30 min SLA
- P3 (ticket): Non-urgent, needs attention → Auto-create Jira → next business day

**Key principle:** Alert on symptoms (user impact), not causes. "5xx rate > 5%" = symptom. "CPU > 80%" = cause (might not affect users).

---

## Section 5: Comparison & Decision-Making

### Q31: Why ALB over NLB?

**Answer:**
| | ALB (Layer 7) | NLB (Layer 4) |
|---|---|---|
| Protocol | HTTP/HTTPS | TCP/UDP/TLS |
| Routing | Path-based, host-based, header-based | Port-based only |
| WAF compatible | ✅ Yes | ❌ No |
| SSL termination | ✅ With rich features | ✅ Basic |
| Health check | HTTP (check endpoint) | TCP (port open?) |
| WebSocket | ✅ Yes | ✅ Yes |
| Speed | Slightly slower (L7 parsing) | Faster (no L7 parsing) |
| Best for | Web apps, APIs, microservices | gRPC, gaming, extreme perf, static IPs |

**Our decision:** ALB — we need path-based routing (`/api/*` vs `/static/*`), WAF integration, and HTTP health checks. NLB would be chosen for gRPC services or when you need static IPs (NLB gives fixed IPs, ALB doesn't).

---

### Q32: Why Aurora over standard RDS MySQL?

**Answer:**
| | RDS MySQL | Aurora MySQL |
|---|---|---|
| Storage | Manual resize (allocate upfront) | Auto-scales 10GB → 128TB |
| Replication | Async read replicas (lag minutes) | Sub-10ms replica lag |
| Failover | 60-120 seconds | < 30 seconds |
| Replicas | Up to 5 | Up to 15 |
| Storage redundancy | 2 AZs (Multi-AZ) | 6 copies across 3 AZs |
| Cost | ~30% cheaper | Premium (~20% more) |
| Performance | Standard | 3-5x faster |

**Decision:** Aurora — the failover speed (<30s vs 120s) was the deciding factor for our 99.95% SLA. Auto-scaling storage eliminates "disk full" emergencies. Worth the ~20% premium.

**When standard RDS wins:** Dev/test environments (cost matters, performance doesn't), or when budget is extremely constrained and 120s failover is acceptable.

---

### Q33: Why EC2 ASG over ECS Fargate?

**Answer:**
- **Context:** Team of 8 engineers, strong EC2/AMI knowledge, no container expertise at the time.
- **Decision:** EC2 ASG with AMI-based deployments (Packer builds AMI → ASG instance refresh).
- **Trade-off:** More operational overhead (patching AMIs, managing instances) but faster to deliver (team already knows this).
- **When I'd choose Fargate today:** New project, team has container knowledge, want zero instance management, simpler scaling (no capacity planning).
- **Migration path:** We're moving to ECS Fargate next quarter (app already containerized for dev, just need prod ECS infrastructure in Terraform).

---

### Q34: Why Terraform modules over flat files?

**Answer:**
- **Without modules (flat):** `prod/main.tf` = 500 lines, `staging/main.tf` = 480 lines (99% copy-paste). Change ALB config → edit in 3 places. Drift between environments.
- **With modules:** `modules/alb/main.tf` = 80 lines. Called from `environments/prod/main.tf` (5 lines) and `environments/staging/main.tf` (5 lines). Change once → all environments consistent.
- **Trade-off:** Initial setup takes longer. Modules need well-defined inputs/outputs. But pays off immediately with 3+ environments.
- **When flat is OK:** Truly one-off infrastructure (single environment, no reuse expected).

---

### Q35: Why 3 AZs instead of 2?

**Answer:**
- **2 AZs:** If one AZ fails, you lose 50% capacity. Remaining AZ must handle 100% traffic. If it's already at 80% → overloaded → cascade failure.
- **3 AZs:** If one AZ fails, you lose 33% capacity. Remaining 2 AZs handle load with 67% capacity available. Much safer margin.
- **Cost difference:** Minimal (one extra NAT Gateway = $35/month, one extra subnet = free).
- **Our design:** ASG min=3 across 3 AZs = 1 instance per AZ. If AZ fails → 2 instances serve (67% capacity) → ASG launches replacement in healthy AZ (back to 3 in 2-3 min).

---

### Q36: Why NAT Gateway per AZ instead of a single shared one?

**Answer:**
- **Single NAT:** Cheaper ($35/month vs $105/month). But if it fails → ALL private subnets lose outbound internet → app can't reach external APIs, can't pull configs, can't report metrics.
- **NAT per AZ:** If NAT in AZ-a fails → only AZ-a private subnet loses outbound. AZ-b and AZ-c still function. Blast radius contained.
- **Real incident:** Early in the project, single NAT had a 5-min blip. All app servers lost connectivity to Secrets Manager → couldn't rotate DB credentials → cascading auth failures. After that, deployed 3 NATs. Never happened again.

---

### Q37: tfsec vs Checkov vs OPA — when to use which?

**Answer:**
| Tool | Focus | Speed | Custom Rules | Best For |
|---|---|---|---|---|
| tfsec | Security-focused | Very fast | Limited | Quick security checks in PR |
| Checkov | CIS benchmarks + compliance | Fast | Python-based | Compliance reporting |
| OPA/Conftest | Custom policies (Rego) | Medium | Unlimited (Rego) | Organization-specific rules |

**Our approach:** All three in sequence.
1. tfsec → catch obvious security issues (open SGs, missing encryption).
2. Checkov → verify CIS/SOC2 compliance posture.
3. OPA → enforce company-specific rules ("all RDS must use CMK, not default key").

**When to skip:** Dev environment PR → tfsec only (fast). Production PR → all three.



---

## Section 6: Behavioral & Leadership

### Q38: How did you convince the team to move from ClickOps to Terraform?

**Answer (STAR):**
- **Situation:** Entire infrastructure was manually configured in AWS console. 3 engineers each had their own way of setting things up. No documentation. New environment took 2 days to create.
- **Task:** Migrate to IaC without disrupting running production.
- **Action:** Didn't ask for a "3-week Terraform migration project." Instead, started with ONE module (VPC) for a NEW staging environment. Showed: "Same VPC in 5 minutes, repeatable, version-controlled." Then Terraform-imported existing prod VPC. Ran `terraform plan` → showed no changes → proved Terraform now manages it without touching anything.
- **Result:** Team saw the value immediately. Within 2 months, all infrastructure was Terraform-managed. New environment creation: 2 days → 30 minutes.

**Learning:** Don't propose a big migration. Demonstrate value on one small, safe thing first.

---

### Q39: Tell me about the NAT Gateway incident and what you learned.

**Answer (STAR):**
- **Situation:** 2 AM alert — all application servers returning 500s. Dashboard showed DB connections fine, CPU fine, but external API calls timing out.
- **Task:** Restore service ASAP, identify root cause.
- **Action:** Traced the issue: app servers in private subnet → outbound through single NAT Gateway → NAT had a service disruption (AWS issue, resolved in 5 min). But 5 minutes of total outbound failure = 5 minutes of app failure.
- **Result:** Immediate fix: AWS resolved. Long-term fix: deployed NAT Gateway per AZ (3 total). Cost: +$70/month. Benefit: single-AZ NAT failure now only affects 1/3 of instances, and even those retry successfully via ALB routing traffic to healthy AZ instances.

**Learning:** Any single shared resource is a SPOF regardless of how reliable AWS says it is. Design for the failure of any single component.

---

### Q40: How did you handle a situation where a developer made manual changes in the AWS console?

**Answer (STAR):**
- **Situation:** After going live with Terraform, discovered a security group rule added manually (port 22 open to 0.0.0.0/0 — developer needed SSH access, added it in console).
- **Task:** Fix the immediate security risk AND prevent recurrence.
- **Action:**
  1. Immediately: Removed the rule manually + via Terraform (`terraform apply` reconciled state).
  2. Set up drift detection: `terraform plan` runs every 6 hours via scheduled pipeline. If drift → Slack alert.
  3. Team discussion (blameless): "Why did they need console access?" → They needed SSH for debugging. Provided SSM Session Manager as alternative (no SG changes needed, audited, logged).
  4. Restricted console write access: Developers got read-only. Changes only through Terraform PRs.
- **Result:** Zero manual console changes since then. SSM adopted for debugging. drift detection caught 2 more cases in staging (alerted, fixed same day).

**Learning:** Blame the process, not the person. They went to console because we didn't provide a better path. Fix the path.

---

### Q41: How did you prioritize between features and infrastructure improvements?

**Answer:**
- **Framework:** Used a "20% infrastructure" rule — every sprint, 20% of capacity allocated to infra improvements (not just feature work).
- **How I got buy-in:** Presented in business terms: "Scheduled scaling saves $200/month. CloudFront reduces latency by 80% → better conversion. WAF prevents the kind of breach that costs $500K+."
- **Prioritization:** Ranked by risk × impact. Security fixes (open SG) = immediate. Performance (CloudFront) = this sprint. Nice-to-have (better tagging) = backlog.
- **Result:** Never had to argue for "infrastructure sprint." Consistent 20% investment prevented tech debt accumulation.

---

### Q42: How do you onboard a new engineer to understand this architecture?

**Answer:**
1. **Architecture diagram session (30 min):** Walk through the flow: user → CloudFront → WAF → ALB → EC2 → Aurora. Explain WHY each component exists.
2. **Terraform code walkthrough (1 hour):** Show module structure, run `terraform plan` on dev — see what "infrastructure as code" means in practice.
3. **Deploy a change (hands-on):** Let them change an ASG parameter in dev, run plan, see the diff, apply it. Learn by doing.
4. **Monitoring tour (30 min):** Show CloudWatch dashboards — "this is how you know the system is healthy."
5. **Incident runbook:** Give them the runbook. Walk through a past incident: "Here's what happened, here's how we diagnosed it."
6. **After 1 week:** They can independently make Terraform changes in dev with confidence.

---

### Q43: Tell me about a time this architecture prevented a security breach.

**Answer (STAR):**
- **Situation:** WAF logs showed a spike in SQL injection attempts against `/api/login` endpoint (2000 blocked requests in 10 minutes from distributed IPs).
- **Task:** Verify the attack was blocked, assess if any bypassed, and strengthen if needed.
- **Action:**
  1. Verified: WAF SQLi rule blocked all attempts (0 reached app servers — confirmed via app logs).
  2. Checked ALB access logs: no 200 responses with suspicious query strings → nothing got through.
  3. Added additional WAF rule: rate limit specifically on `/api/login` (100 req/min/IP — stricter than global limit).
  4. Reported to security team: provided WAF logs as evidence for SOC2 audit trail.
- **Result:** Zero impact. Attack fully mitigated by existing WAF rules. Additional rate limiting added for defence in depth. Used as evidence in quarterly security review: "This is why WAF investment pays off."

---

## Section 7: Future & Improvements

### Q44: What's on your roadmap for improving this architecture?

**Answer:**
| Priority | Improvement | Why |
|---|---|---|
| 1 | Migrate to ECS Fargate | Eliminate AMI patching, faster scaling (seconds not minutes), better resource efficiency |
| 2 | Add ElastiCache Redis | Reduce DB load by 60-70% for read-heavy endpoints (product catalog, sessions) |
| 3 | VPC Endpoints (S3, Secrets Manager) | Eliminate NAT Gateway data transfer cost, improve security (private path) |
| 4 | AWS Config rules + auto-remediation | If SG opens to 0.0.0.0/0 → Lambda auto-removes the rule |
| 5 | Graviton instances (ARM) | 20% better price/performance than x86 m5 instances |
| 6 | Global Accelerator | Consistent low-latency for global users (vs CloudFront for dynamic content) |
| 7 | Blue-Green deployment (in addition to rolling) | For major releases requiring instant rollback |

---

### Q45: What's the technical debt in this architecture?

**Answer:**
1. **EC2 instead of containers** — More operational overhead. AMI patching cycle needed monthly.
2. **No ElastiCache** — Every request hits Aurora. At 10x scale, DB becomes bottleneck.
3. **NAT Gateway data transfer costs** — S3 and Secrets Manager calls go through NAT (expensive). VPC endpoints would save ~$50/month.
4. **Single-region primary** — If us-east-1 goes down, DR (Pilot Light) takes 5 min. Active-Active would be better but costs 2x.
5. **No service mesh** — Direct instance-to-instance communication without mTLS. Fine for current scale, not for microservices.
6. **Terraform state in S3 same account** — Should be in a dedicated management account for true blast radius isolation.

---

### Q46: If budget doubled, what would you add?

**Answer:**
1. **Active-Active DR** — Full stack in second region, Aurora Global Database, Route53 latency-based routing. RTO → 0.
2. **ECS Fargate** — Containerized workloads, faster deployments, Spot for non-critical tasks.
3. **AWS Shield Advanced** — Enhanced DDoS protection with dedicated response team.
4. **ElastiCache cluster** — Multi-AZ Redis for sessions, caching, and rate limiting.
5. **AWS Backup centralized** — Automated backup plan with cross-region copy.
6. **Chaos Engineering (AWS FIS)** — Regular fault injection to validate HA assumptions.

---

### Q47: How would microservices change this architecture?

**Answer:**
If the monolith is decomposed into microservices:

| Current (Monolith) | Microservices Change |
|---|---|
| Single ALB target group | Multiple target groups (per service) + path-based routing |
| One ASG (3-20 instances) | Multiple ASGs or ECS services (one per microservice) |
| Single Aurora DB | Database per service (each service owns its data) |
| Direct app-to-DB | API Gateway → service mesh → each service → its own DB |
| One deployment pipeline | Pipeline per service (independent releases) |
| Shared logging | Distributed tracing (X-Ray) to follow requests across services |

**Key architecture additions:**
- API Gateway (Kong/AWS API GW) for routing + auth + rate limiting.
- Service discovery (Cloud Map or ECS service connect).
- Event bus (EventBridge/SQS) for async communication.
- Distributed tracing (X-Ray) to debug cross-service requests.

---

### Q48: What cost optimization can you do without sacrificing availability?

**Answer:**
| Optimization | Savings | Risk |
|---|---|---|
| Scheduled scaling (2 instances at night) | ~$100/mo | Low — traffic is negligible at night |
| Savings Plan (1-year compute) | ~35% on EC2/Fargate | Lock-in to instance family |
| Graviton (m6g instead of m5) | ~20% price/performance | Need to test app on ARM |
| S3 Intelligent-Tiering for logs | ~$20/mo | None — automatic |
| VPC Endpoints for S3 | ~$40/mo NAT savings | None — better security too |
| Reserved capacity for RDS | ~40% off Aurora | Lock-in to instance class |
| CloudFront caching optimization | ~$15/mo (less origin traffic) | None — faster for users |
| **Total potential savings** | **~$250-300/month** | Minimal |

---

## Bonus: Cross-Cutting Questions

### Q49: How do you handle database schema migrations in this architecture?

**Answer:**
- **Tool:** Flyway (Java) / Alembic (Python) — version-controlled SQL migrations.
- **Strategy:** Expand-and-contract pattern:
  1. Add new column (backward compatible — old code ignores it).
  2. Deploy new code that uses new column.
  3. Migrate data from old column to new column.
  4. Drop old column (separate release, after verification).
- **Why:** Allows rollback at any step without data loss. Never make breaking schema changes in one release.
- **Pipeline integration:** Migration runs as first step in deploy (before app restart). If migration fails → deployment aborts.

---

### Q50: How do you handle secrets in this architecture?

**Answer:**
| Secret | Storage | Rotation |
|---|---|---|
| RDS password | AWS Secrets Manager | Auto-rotated every 30 days (Lambda) |
| API keys (external services) | Secrets Manager | Manual, on personnel change |
| TLS certificates | ACM (auto-renewed) | Automatic (AWS manages) |
| SSH keys | Not used — SSM Session Manager | N/A |
| Terraform state encryption key | KMS CMK | Annual rotation |

**App reads secrets at boot:** EC2 instance profile → IAM role → GetSecretValue API → inject into app config. No secrets in AMI, no secrets in environment variables baked at build time.

---

### Q51: What compliance frameworks does this architecture satisfy?

**Answer:**
| Framework | How Architecture Satisfies |
|---|---|
| SOC2 — Access Control | SG chaining, IAM roles, no public DB access |
| SOC2 — Change Management | Terraform PRs, IaC scanning, approval workflow |
| SOC2 — Monitoring | CloudWatch alarms, VPC Flow Logs, CloudTrail |
| SOC2 — Availability | Multi-AZ, ASG, Aurora failover, DR strategy |
| PCI-DSS Req 1 | WAF + SG chaining + NACLs (network segmentation) |
| PCI-DSS Req 3 | KMS encryption at rest |
| PCI-DSS Req 4 | TLS 1.2+ everywhere (in transit) |
| PCI-DSS Req 10 | CloudTrail + ALB access logs + VPC Flow Logs (audit trail) |
| HIPAA | Encryption + access controls + audit logging + BAA with AWS |

---

*End of Q&A Bank — 51 questions covering all 7 dimensions*
