# Project 5: Serverless Event-Driven Architecture

## Serverless Operations Automation Platform — Self-Healing Infrastructure

**Author:** Siddharth Patel  
**Role:** Staff/Principal DevOps & Cloud Engineer (12 YOE)  
**Technologies:** AWS Lambda, API Gateway, EventBridge, Step Functions, DynamoDB, S3, SQS, SNS, SAM, CloudWatch, AWS Config

---

## Table of Contents

1. What is Serverless?
2. When Serverless vs Containers vs VMs
3. Event-Driven Architecture (Simple Explanation)
4. Project: Automated Security Remediation Engine
5. How Each Component Works (Simple English)
6. Security
7. Monitoring & Logging
8. Cost Comparison
9. Limitations & Gotchas
10. Interview Talking Points

---

## 1. What is Serverless?

**You write code. Cloud runs it. You pay only when it executes. No servers to manage.**

**Simple analogy:** 
- VMs = Owning a car (you pay insurance, fuel, maintenance even when parked)
- Containers = Renting a car daily (cheaper, but still pay per day)
- Serverless = Taking a taxi (pay only per ride, zero cost when not riding)

**What "serverless" really means:**
- Servers exist — you just don't see or manage them
- No patching, no scaling config, no capacity planning
- Scales from 0 to 10,000 concurrent automatically
- Pay per request ($0.20 per 1 million requests) + compute time
- Zero traffic = $0 cost (unlike EC2 running 24/7)

---

## 2. When Serverless vs Containers vs VMs

| Factor | Serverless (Lambda) | Containers (EKS) | VMs (EC2) |
|---|---|---|---|
| **Best for** | Event-driven, short tasks, variable traffic | Long-running, microservices, steady traffic | Legacy, full OS control, GPU |
| **Max execution** | 15 minutes | Unlimited | Unlimited |
| **Scaling** | Instant (0 → 1000 in seconds) | Fast (30s pods, 60s nodes) | Slow (2-5 min) |
| **Cold start** | 100ms-2s (first request after idle) | None (always running) | None (always running) |
| **Cost at low traffic** | Near $0 | ~$150/mo minimum (nodes running) | ~$70/mo minimum (1 instance) |
| **Cost at high traffic** | Expensive (per-request adds up) | Cheaper (fixed node cost) | Cheapest (reserved) |
| **Ops burden** | Zero (no patching, no scaling) | Medium (cluster, upgrades) | High (OS, patches, scaling) |
| **State** | Stateless (no local disk between calls) | Stateful possible (PVs) | Full state (disk, memory) |

### Decision Rule

```
Is execution < 15 min?
  └── YES → Is traffic variable/unpredictable?
                └── YES → Is cold start OK (not sub-10ms)?
                            └── YES → SERVERLESS ✅
                            └── NO  → CONTAINERS (always warm)
                └── NO (steady high traffic) → CONTAINERS (cheaper)
  └── NO → CONTAINERS or VMs
```

---

## 3. Event-Driven Architecture (Simple Explanation)

### What is it?

Instead of apps constantly asking "is there work?" (polling), events TRIGGER functions automatically.

**Traditional (request-driven):**
```
User → App (always running, waiting) → DB
       ↑ App is running 24/7 even if nobody makes requests
```

**Event-driven:**
```
Event happens → Lambda runs → Does work → Dies
                (only exists for the 200ms it takes to process)
```

**Simple analogy:**
- Traditional = Security guard sitting 24/7 watching monitors (paid even when nothing happens)
- Event-driven = Motion sensor + alarm (only activates when something happens, zero cost otherwise)

---

## 4. Project: Automated Security Remediation Engine

### Problem Statement

Our Landing Zone (Project 4) has SCPs that PREVENT certain actions. But SCPs can't cover everything — they block actions, they can't FIX violations that already exist or slip through.

**Example:** Someone creates a Security Group with SSH open to the world. SCP can block this, BUT:
- What if the SCP wasn't applied to that OU yet?
- What about existing resources created before the SCP?
- What about resources created by automation that needs temporary access?

**We need:** A system that DETECTS and auto-FIXES security violations in real-time — without any human intervention.

### What We Built

An automated engine that:
1. **Detects** security violations (AWS Config rules watch for bad configurations)
2. **Routes** events to the correct handler (EventBridge matches patterns)
3. **Buffers** events for reliability (SQS ensures no event is lost)
4. **Remediates** automatically (Lambda fixes the violation)
5. **Logs** every action (DynamoDB audit trail)
6. **Notifies** the team (SNS → Slack + PagerDuty)
7. **Reports** weekly compliance status (EventBridge schedule → Lambda → S3)
8. **Provides dashboard** (API Gateway → Lambda → DynamoDB query)

### How It Connects to Projects 1-4

```
Project 4 (Landing Zone): SCPs PREVENT violations → This project FIXES ones that slip through
Project 2 (3-Tier AWS):   Detects open SGs, unencrypted disks in your infrastructure
Project 3 (EKS):          Detects public load balancers, excessive permissions
Project 1 (CI/CD):        Dashboard shows remediation history (deployable via same pipeline)
```

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│ DETECT (What's watching for violations?)                              │
│                                                                      │
│  AWS Config Rules:                                                   │
│    • "Security Group should not allow 0.0.0.0/0 on port 22"        │
│    • "S3 bucket should not be public"                                │
│    • "EBS volume should be encrypted"                                │
│    • "RDS should not be publicly accessible"                         │
│                                                                      │
│  When violated → Config sends event                                  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ (event: "sg-123 is NON_COMPLIANT")
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ ROUTE (Who decides where this event goes?)                           │
│                                                                      │
│  EventBridge Rule:                                                   │
│    IF source = "aws.config"                                          │
│    AND detail.configRuleName = "sg-ssh-open-*"                      │
│    THEN → send to SQS queue "sg-remediation-queue"                  │
│                                                                      │
│  EventBridge Rule:                                                   │
│    IF source = "aws.config"                                          │
│    AND detail.configRuleName = "s3-public-*"                        │
│    THEN → send to SQS queue "s3-remediation-queue"                  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ BUFFER (What if Lambda is busy or fails?)                            │
│                                                                      │
│  SQS Queue: "sg-remediation-queue"                                  │
│    • Holds the event until Lambda is ready                           │
│    • If Lambda fails → retries 3 times                              │
│    • After 3 failures → sends to Dead Letter Queue (DLQ)            │
│    • DLQ alarm → pages the team (something is really broken)        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ REMEDIATE (What fixes the problem?)                                  │
│                                                                      │
│  Lambda Function: "sg-remediation"                                   │
│    1. Read event from SQS → get Security Group ID                   │
│    2. Call EC2 API → remove the bad rule (0.0.0.0/0 on port 22)    │
│    3. Log action to DynamoDB (who, what, when)                      │
│    4. Send notification to SNS topic                                 │
│    Execution time: ~2 seconds | Cost: $0.0000002                    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ LOG + NOTIFY (How do we track and inform?)                           │
│                                                                      │
│  DynamoDB Table: "remediation-audit"                                 │
│    • Every action recorded with timestamp, resource, action taken    │
│                                                                      │
│  SNS Topic: "security-notifications"                                 │
│    ├──→ Slack webhook (#security channel): "🔒 Fixed: SG open SSH" │
│    ├──→ Email (security team): Weekly digest                        │
│    └──→ PagerDuty (only if GuardDuty critical finding)              │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ REPORT + DASHBOARD (How do humans see the status?)                   │
│                                                                      │
│  EventBridge Schedule (weekly, Monday 9 AM):                         │
│    → Lambda generates compliance report → saves to S3               │
│    → SNS sends report link to team leads                             │
│                                                                      │
│  API Gateway + Lambda (on-demand dashboard):                         │
│    GET /remediations?last=7days → Lambda queries DynamoDB → returns │
│    "Fixed 23 violations this week. 0 in DLQ. 100% auto-resolved."  │
└──────────────────────────────────────────────────────────────────────┘
```

### The Complete Flow (One Event, Start to Finish)

```
Someone opens SSH (port 22) to 0.0.0.0/0 on a Security Group
    │
    │ (within 1 minute)
    ▼
AWS Config detects: "sg-0abc123 is NON_COMPLIANT for rule restricted-ssh"
    │
    │ (event published)
    ▼
EventBridge matches rule: source=aws.config, ruleName=restricted-ssh
    │
    │ (routes to target)
    ▼
SQS Queue receives message (buffered, guaranteed delivery)
    │
    │ (Lambda polls queue)
    ▼
Lambda "sg-remediation" runs:
    • Reads: sg-0abc123 has 0.0.0.0/0 on port 22
    • Action: ec2.revoke_security_group_ingress(sg-0abc123, port 22, 0.0.0.0/0)
    • Logs: DynamoDB ← {time, sg-0abc123, "removed SSH open rule", SUCCESS}
    • Notifies: SNS ← "🔒 Auto-fixed: sg-0abc123 had SSH open to world"
    │
    │ (2 seconds total)
    ▼
DONE. Security Group is safe. Team notified. Audit trail stored.
Total time from violation to fix: ~90 seconds. Zero human involved.
```

---

## 5. How Each Component Works (Simple English)

### EventBridge — The Post Office

**What it is:** A service that receives events and delivers them to the right destination based on rules.

**Simple analogy:** A post office. Letters (events) arrive. Post office reads the address (rule matching) and delivers to the correct house (target: Lambda, SQS, SNS).

**How we use it:**
```
Event arrives: { source: "aws.config", detail: { ruleViolated: "restricted-ssh" } }

Rule says: "If source is aws.config AND rule is restricted-ssh → send to SQS queue"

Result: Event lands in the SQS queue automatically
```

**Why not trigger Lambda directly from Config?**
- EventBridge is decoupled — Config doesn't know or care who handles the event
- We can add MORE targets later without changing Config (e.g., also log to S3)
- We can FILTER — only route CRITICAL violations to PagerDuty, INFO to Slack
- We can schedule events (daily cert scan) — Config can't do that

**Real-world example:** 
TV remote (EventBridge) → you press "volume up" (event) → TV receives it (target). If you buy a soundbar, you just program the remote to also send to soundbar. TV doesn't change.

---

### Lambda — The Worker

**What it is:** A function that runs your code ONLY when triggered. It starts, does work, and dies. You pay only for the seconds it runs.

**Simple analogy:** A temp worker. You call the agency (trigger), worker arrives (cold start ~200ms), does the job (execution), leaves (dies). You only pay for the minutes they worked. No salary when no work exists.

**How we use it:**
```python
def handler(event, context):
    # 1. Read what happened
    sg_id = event['Records'][0]['body']  # from SQS message
    
    # 2. Fix it
    ec2.revoke_security_group_ingress(GroupId=sg_id, ...)
    
    # 3. Log it
    dynamodb.put_item(TableName='audit', Item={...})
    
    # 4. Notify
    sns.publish(TopicArn='...', Message=f'Fixed {sg_id}')
    
    return {'statusCode': 200}
```

**Key settings for our Lambda:**
| Setting | Value | Why |
|---|---|---|
| Memory | 256 MB | Small function, doesn't need much |
| Timeout | 30 seconds | Remediation takes 2-5s, 30s gives buffer for retries |
| Runtime | Python 3.12 | Boto3 (AWS SDK) included by default |
| Concurrency | 10 | Don't want 1000 remediations simultaneously (rate limit protection) |

**What happens on failure?** Lambda returns error → SQS makes message visible again → Lambda retries. After 3 failures → message goes to DLQ (Dead Letter Queue) → CloudWatch alarm → team paged.

---

### SQS — The Queue (Buffer)

**What it is:** A message queue that holds events until a consumer (Lambda) is ready to process them.

**Simple analogy:** A restaurant order ticket system. Waiter (EventBridge) writes order on ticket, puts on the line (queue). Chef (Lambda) picks up tickets one at a time. If chef is busy, tickets wait safely. If chef burns a dish, ticket goes back on the line (retry). If chef fails 3 times, ticket goes to the manager (DLQ).

**Why we need it between EventBridge and Lambda:**
1. **Reliability:** If Lambda crashes, message stays in queue (not lost)
2. **Retry:** Failed processing? SQS makes message visible again after 30s
3. **Backpressure:** 100 events arrive in 1 second? Queue holds them, Lambda processes at its pace
4. **Dead Letter Queue:** After 3 failures, message goes to DLQ for human investigation

**SQS Configuration:**
```
Main Queue: "sg-remediation-queue"
  Visibility Timeout: 60 seconds (if Lambda doesn't finish in 60s, retry)
  Max Receive Count: 3 (after 3 failures → DLQ)

Dead Letter Queue: "sg-remediation-dlq"
  Retention: 14 days (gives team time to investigate)
  Alarm: ANY message in DLQ → CloudWatch Alarm → PagerDuty
```

**Without SQS (risky):**
```
EventBridge → Lambda directly
  Problem: If Lambda fails, event is LOST. No retry. No record.
```

**With SQS (safe):**
```
EventBridge → SQS → Lambda
  If Lambda fails: message becomes visible again → retries
  If Lambda fails 3 times: message → DLQ → team investigates
  Event is NEVER lost
```

---

### DynamoDB — The Audit Log

**What it is:** A serverless database. No servers to manage, scales infinitely, single-digit millisecond reads.

**Simple analogy:** A self-expanding filing cabinet. You put files in, it grows automatically. You can find any file in under 10ms. You never reorganize drawers — it does it for you. You pay per read/write (not per hour running).

**How we use it (audit trail):**

Every remediation action creates a record:
```json
{
  "event_id": "evt-abc123",
  "timestamp": "2026-07-22T12:30:00Z",
  "resource_type": "SecurityGroup",
  "resource_id": "sg-0abc123",
  "violation": "SSH open to 0.0.0.0/0",
  "action_taken": "Removed ingress rule for port 22 from 0.0.0.0/0",
  "status": "SUCCESS",
  "lambda_function": "sg-remediation",
  "account_id": "123456789012",
  "region": "us-east-1"
}
```

**Why DynamoDB (not RDS/PostgreSQL)?**
- Serverless → no database server to manage
- Auto-scales → handles 10 writes/day or 10,000 writes/day without config
- Pay per request → $0 if no violations (no idle cost)
- Fast → dashboard queries take <10ms

---

### SNS — The Notification Hub

**What it is:** Pub/Sub (publish/subscribe). One message published → delivered to ALL subscribers simultaneously.

**Simple analogy:** A radio station. Station broadcasts once (publish). Every radio tuned to that frequency (subscribers) hears it at the same time. You don't need to call each person individually.

**How we use it:**
```
Lambda publishes: "🔒 Auto-fixed: sg-0abc123 had SSH open to world"
    │
    ├──→ Subscriber 1: Slack webhook → posts to #security channel
    ├──→ Subscriber 2: Email → security-team@company.com
    └──→ Subscriber 3: PagerDuty (only for critical/GuardDuty events)
```

**Why SNS instead of Lambda calling Slack directly?**
- **Decoupled:** Lambda doesn't know or care who gets notified. Add/remove subscribers without code changes.
- **Fan-out:** One publish → many destinations simultaneously.
- **Reliability:** SNS retries delivery if Slack webhook is temporarily down.
- **Filtering:** Subscribers can filter (PagerDuty only gets `severity=critical` messages).

---

### API Gateway — The Dashboard Door

**What it is:** A managed HTTP endpoint. Receives HTTP requests and routes them to Lambda.

**Simple analogy:** A hotel reception desk. Guest (user) arrives, says "I need information about remediation history." Receptionist (API Gateway) calls the right staff member (Lambda) to prepare the answer.

**How we use it (compliance dashboard API):**
```
GET https://api.company.com/remediations?days=7

→ API Gateway receives request
→ Validates: Is caller authenticated? (IAM or API key)
→ Routes to: Lambda "dashboard-query"
→ Lambda queries DynamoDB: last 7 days of remediations
→ Returns JSON: { "total": 23, "types": {"sg": 15, "s3": 5, "ebs": 3}, "dlq": 0 }
```

**Why API Gateway (not just query DynamoDB directly)?**
- Authentication (don't expose DB to world)
- Rate limiting (prevent abuse)
- Caching (same query doesn't hit DB repeatedly)
- Transform response (DB format → clean JSON for frontend)

---

### S3 — The Report Storage

**What it is:** Object storage. Store any file (reports, backups, logs). Infinitely scalable, 11 nines durability.

**Simple analogy:** A warehouse with unlimited shelves. Put anything in, find it by name. It will never lose your stuff (99.999999999% durability). Pay only for what you store.

**How we use it:**
- Weekly compliance reports (HTML) generated by scheduled Lambda → stored in S3
- Historical audit exports (for external auditors)
- DLQ investigation records

---

### EventBridge Schedule — The Cron Job

**What it is:** Triggers a Lambda on a schedule (like cron, but serverless).

**Simple analogy:** An alarm clock. Set it to ring at 9 AM every Monday → Lambda wakes up, generates weekly report, goes back to sleep.

**How we use it:**
```
Rule: "Every Monday 9 AM UTC"
Target: Lambda "weekly-compliance-report"

Lambda runs:
  1. Query DynamoDB: all remediations this week
  2. Generate HTML report (violations found, fixed, pending)
  3. Save to S3
  4. Publish to SNS: "Weekly Security Report: 23 violations auto-fixed, 0 in DLQ"
```

**Cost:** $0. EventBridge rules are free. Lambda runs once per week = $0.0000004.

---

## 6. Security

| Layer | How | Why |
|---|---|---|
| Lambda IAM role | Least privilege — sg-remediation Lambda can ONLY modify security groups, nothing else | If Lambda is compromised, blast radius is limited |
| API Gateway auth | IAM authentication (SigV4) for dashboard | Only authorized users see remediation data |
| DynamoDB encryption | Encrypted at rest (AWS-managed KMS key) | Audit data is sensitive |
| Secrets | Slack webhook URL in Secrets Manager (not env var) | Env vars visible in console; Secrets Manager is encrypted + audited |
| SQS encryption | Server-side encryption (SSE-SQS) | Messages contain resource IDs |
| VPC | Lambda does NOT run in VPC (doesn't need private network access) | Avoids cold start penalty (VPC Lambda adds 1-5s) |
| Concurrency limit | Lambda max concurrency = 10 | Prevents runaway remediation (e.g., bug that deletes all SGs) |

---

## 7. Monitoring & Logging

### Metrics We Watch

| Metric | Source | Alert When |
|---|---|---|
| Remediations/day | DynamoDB item count | Spike > 50/day (unusual — possible attack or misconfiguration) |
| DLQ message count | SQS DLQ | > 0 (something is failing repeatedly) |
| Lambda errors | CloudWatch | > 0 errors in 5 min |
| Lambda duration | CloudWatch | P99 > 10 seconds (getting slow) |
| Config rule compliance | AWS Config | Any rule < 100% compliance for > 1 hour |

### Tracing with X-Ray

```
Event detected (0ms)
    → EventBridge routing (5ms)
    → SQS delivery (10ms)
    → Lambda execution:
        ├── Read SQS message (2ms)
        ├── EC2 API call: revoke SG rule (800ms)
        ├── DynamoDB put_item (5ms)
        └── SNS publish (10ms)
    → Total: ~830ms
```

X-Ray shows exactly where time is spent. If EC2 API takes 5 seconds instead of 800ms → API throttling. Fix: request limit increase or add exponential backoff.

---

## 8. Cost Comparison

### This Project's Monthly Cost

| Component | Usage | Monthly Cost |
|---|---|---|
| Lambda | ~1000 invocations/month × 2s each | $0.04 |
| SQS | ~1000 messages/month | $0.00 (free tier) |
| DynamoDB | ~1000 writes + 500 reads/month | $0.01 |
| EventBridge | Rules (free) + events | $0.00 |
| SNS | ~1000 notifications | $0.01 |
| S3 | ~50MB reports | $0.01 |
| API Gateway | ~500 dashboard requests | $0.002 |
| **TOTAL** | | **~$0.07/month** |

### If We Built This With Containers Instead

| Component | Container Approach | Monthly Cost |
|---|---|---|
| ECS Fargate (always running, polling for events) | 1 task × 24/7 | ~$35 |
| RDS (PostgreSQL for audit) | db.t3.micro | ~$15 |
| ALB (for dashboard) | Always running | ~$25 |
| **TOTAL** | | **~$75/month** |

**Serverless is 1000x cheaper** for this use case because events are sporadic (5-50/day). Container sits idle 99% of the time but still costs money.

---

## 9. Limitations & Gotchas

| Limitation | Impact on Our Project | Workaround |
|---|---|---|
| 15 min max execution | Not an issue (remediations take 2-5 seconds) | Would use Step Functions if needed |
| Cold start (200ms) | Acceptable — remediation doesn't need sub-ms response | Not latency-sensitive |
| Concurrency limit (1000 default) | If 1000 violations happen simultaneously... | Set reserved concurrency = 10 (intentional limit for safety) |
| Stateless | Can't remember previous events | DynamoDB stores all state |
| Debugging harder | Can't SSH into Lambda | X-Ray + structured CloudWatch logs |
| Vendor lock-in | Tied to AWS EventBridge, Lambda, Config | Acceptable — this is AWS-native automation |

---

## 10. Interview Talking Points

### 2-Minute Version

"Built a serverless security remediation engine that auto-fixes AWS Config violations in real-time. AWS Config detects violations (open security groups, public S3, unencrypted EBS), EventBridge routes events to SQS for reliable buffering, Lambda functions remediate within 90 seconds — no human needed. Every action logged to DynamoDB as audit trail, SNS fans out notifications to Slack and PagerDuty. Weekly compliance reports generated via scheduled Lambda and stored in S3. Dashboard via API Gateway lets the security team query history. The entire system costs $0.07/month because serverless charges per-execution — versus $75/month if we'd used containers. This project directly supports our Landing Zone (Project 4) — SCPs prevent violations, this engine fixes ones that slip through."

### How This Connects to Other Projects

```
Project 4 (Landing Zone) → SCPs PREVENT violations
This Project (Serverless) → FIXES violations that slip through
Together = Defence in Depth (prevent + detect + remediate)
```

### Key Interview Q&A

**Q: "Why serverless for this?"**  
A: Events are sporadic (5-50/day). Each takes 2 seconds. A container sitting 24/7 for 5 events = $75 wasted. Lambda runs 2 seconds, costs $0.0000002 per event. Total: $0.07/month. Zero servers to patch, zero scaling to configure.

**Q: "What if the Lambda itself has a bug and makes things worse?"**  
A: Three safety nets. (1) Concurrency limit = 10 (can't run away). (2) IAM role is least-privilege (sg-remediation Lambda can ONLY modify SGs, nothing else). (3) DLQ — if it fails 3 times, stops trying and pages the team.

**Q: "Why SQS between EventBridge and Lambda?"**  
A: Reliability. Without SQS: Lambda fails → event lost forever. With SQS: Lambda fails → message retries 3 times → if still failing, goes to DLQ (never lost). Also provides backpressure — 100 events arrive at once, Lambda processes at its own pace.

**Q: "How do you test this?"**  
A: SAM CLI locally — `sam local invoke` with sample Config event. Integration test: intentionally create bad SG in staging → verify Lambda remediates within 60 seconds → verify DynamoDB record → verify Slack notification. Takes 2 minutes end-to-end.

**Q: "What about false positives — Lambda removing a legitimate rule?"**  
A: The Config rules define what's "non-compliant." SSH from 0.0.0.0/0 is ALWAYS wrong in our environment. For edge cases (e.g., specific IPs that need access), we use resource exclusions in the Config rule — those are never flagged, never remediated.
