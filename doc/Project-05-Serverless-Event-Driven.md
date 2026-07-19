# Project 5: Serverless Event-Driven Architecture

## Building Without Servers — Lambda, API Gateway, DynamoDB

**Author:** Siddharth Patel  
**Role:** Staff/Principal DevOps & Cloud Engineer (12 YOE)  
**Technologies:** AWS Lambda, API Gateway, DynamoDB, S3, SQS, SNS, EventBridge, SAM

---

## Table of Contents

1. What is Serverless?
2. When Serverless vs Containers vs VMs
3. Event-Driven Architecture (Simple Explanation)
4. Project Architecture
5. Components Explained
6. Security
7. Monitoring & Logging
8. Cost Comparison (Serverless vs Containers)
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

### Real Example: Order Processing

```
Customer places order (API call)
    │
    ▼
API Gateway → Lambda (validate order) → DynamoDB (save order)
                                              │
                                              ▼ (DynamoDB Stream event)
                                        Lambda (process payment)
                                              │
                                              ▼ (success event)
                                   ┌──────────┼──────────┐
                                   │          │          │
                            SQS Queue    SQS Queue    SNS Topic
                                │          │          │
                                ▼          ▼          ▼
                         Lambda      Lambda      Email/SMS
                         (ship)      (invoice)   (notify customer)
```

**Each Lambda:** Only runs when triggered. Only exists for milliseconds. Only pays for compute used.

---

## 4. Project Architecture

### What We Built: Image Processing Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  USER-FACING API                                         │
│                                                          │
│  Route53 → API Gateway (REST) → Lambda (CRUD)           │
│                                     │                    │
│                                     ▼                    │
│                               DynamoDB (metadata)        │
└───────────────────────────────┬─────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────┐
│  EVENT-DRIVEN BACKEND                                    │
│                                                          │
│  S3 Upload Event → Lambda (resize/thumbnail)             │
│       │                    │                             │
│       ▼                    ▼                             │
│  EventBridge         S3 (processed/)                     │
│       │                                                  │
│       ├──→ SQS → Lambda (generate PDF report)           │
│       │                                                  │
│       └──→ SNS → Email notification to user              │
└──────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────┐
│  MONITORING                                              │
│                                                          │
│  CloudWatch Metrics → Alarms → SNS → PagerDuty          │
│  X-Ray (distributed tracing across Lambdas)              │
│  CloudWatch Logs (each Lambda auto-logs)                 │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Components Explained

### API Gateway

**What:** Managed HTTP endpoint that routes requests to Lambda functions.

**Analogy:** Hotel reception desk. Receives all guests (requests), checks their reservation (auth), and directs them to the right room (Lambda).

**Features:**
- Rate limiting (1000 req/sec per client)
- Authentication (Cognito JWT or API keys)
- Request validation (reject malformed before Lambda runs)
- Caching (reduce Lambda invocations for repeated requests)
- Throttling (protect backend from overload)

### Lambda

**What:** Function that runs your code when triggered. Lives for the duration of one request, then dies.

**Analogy:** A temp worker. You call agency (trigger), worker arrives (cold start), does the job (execution), leaves (dies). You only pay for hours worked.

**Key settings:**
- Memory: 128MB → 10GB (more memory = more CPU automatically)
- Timeout: 1s → 15 min max
- Concurrency: 1000 default per region (can increase)
- Layers: Shared libraries (don't include in every function)

### DynamoDB

**What:** Serverless NoSQL database. No capacity planning, scales infinitely, single-digit millisecond latency.

**Analogy:** A magical filing cabinet that grows as you add files, never gets slower, and you pay per read/write.

**When to use:** Simple access patterns (get item by ID, query by date range). NOT for complex joins or analytics.

**Capacity modes:**
- On-demand: Pay per request. Best for unpredictable traffic.
- Provisioned: Set read/write capacity. Cheaper for steady traffic.

### SQS (Simple Queue Service)

**What:** Message queue. Decouples producers from consumers.

**Analogy:** A mailbox. Sender drops letter (message). Receiver picks up when ready. If receiver is busy, letters wait safely.

**Why use between Lambdas?**
- Lambda A finishes instantly → puts message in queue → done
- Lambda B processes at its own pace (doesn't slow A down)
- If B fails, message stays in queue → retries automatically
- If B crashes for hours, messages pile up safely → processed later

### SNS (Simple Notification Service)

**What:** Pub/Sub — one message fans out to many subscribers.

**Analogy:** Radio broadcast. Station (publisher) sends once. All radios tuned in (subscribers) hear it simultaneously.

**Use:** Order placed → SNS → simultaneously: email, SMS, Slack, SQS queues for different services.

### EventBridge

**What:** Event bus that routes events to targets based on rules.

**Analogy:** Air traffic control. Planes (events) arrive, controller (rules) directs each to correct runway (target Lambda/SQS/SNS).

**Better than direct triggers because:**
- Decoupled — source doesn't know who consumes
- Filter — only route events matching pattern
- Multiple targets — one event triggers many actions
- Scheduled — cron-like triggers (every 5 min, daily at 9 AM)

---

## 6. Security

| Layer | How |
|---|---|
| API Authentication | Cognito User Pool (JWT tokens) or API Keys |
| Authorization | IAM policies per Lambda (least privilege) |
| Rate limiting | API Gateway throttling (per client, per endpoint) |
| Input validation | API Gateway request schema validation |
| Data encryption | DynamoDB: encrypted at rest (KMS). S3: SSE-KMS |
| Transport | HTTPS only (API GW enforces TLS 1.2) |
| Secrets | Lambda reads from Secrets Manager at runtime (cached) |
| Network | Lambda in VPC (if needs DB access). Otherwise no VPC needed |
| Logging | Every invocation auto-logged to CloudWatch |
| Dead Letter Queue | Failed events go to DLQ — don't lose data |

---

## 7. Monitoring & Logging

### Metrics (Auto-Collected)

| Metric | What It Tells You | Alert When |
|---|---|---|
| Invocations | How many times Lambda ran | Unexpected spike (DDoS?) |
| Errors | Failed executions | >1% error rate |
| Duration | How long each execution takes | P99 > 5 seconds |
| Throttles | Requests rejected (concurrency limit) | >0 (need increase or fix) |
| ConcurrentExecutions | How many running now | >80% of limit |
| Iterator Age (SQS) | How old is the oldest unprocessed message | >60 seconds (consumer too slow) |

### Distributed Tracing (X-Ray)

```
API GW (50ms) → Lambda-validate (30ms) → DynamoDB (5ms)
                      │
                      └→ SQS (2ms) → Lambda-process (200ms) → S3 (20ms)
```

X-Ray shows the FULL request journey across all services with timing per hop. Instantly find bottlenecks.

### Logging

- Each Lambda auto-creates CloudWatch Log Group
- Structured JSON logs (parse with Log Insights)
- Retention: 14 days (set policy, default is forever = expensive!)
- DLQ monitoring: Alert if ANY message lands in DLQ (something failed)

---

## 8. Cost Comparison

### Scenario: API serving 1 million requests/month

| Component | Serverless Cost | Container (EKS) Cost |
|---|---|---|
| Compute | Lambda: ~$3.50 | 2x t3.medium 24/7: ~$60 |
| Database | DynamoDB on-demand: ~$5 | RDS t3.small: ~$30 |
| API layer | API Gateway: ~$3.50 | ALB: ~$25 |
| Monitoring | CloudWatch: ~$5 | Prometheus (self-hosted): $0 |
| **Total** | **~$17/month** | **~$115/month** |

### Scenario: API serving 100 million requests/month

| Component | Serverless Cost | Container (EKS) Cost |
|---|---|---|
| Compute | Lambda: ~$350 | 6x m5.large: ~$420 |
| Database | DynamoDB: ~$500 | RDS r5.large: ~$400 |
| API layer | API Gateway: ~$350 | ALB: ~$50 |
| **Total** | **~$1,200/month** | **~$870/month** |

**Crossover point:** ~10-50 million requests/month. Below that → serverless cheaper. Above that → containers cheaper.

---

## 9. Limitations & Gotchas

| Limitation | Impact | Workaround |
|---|---|---|
| 15 min max execution | Can't run long batch jobs | Step Functions (chain Lambdas) |
| Cold starts (100ms-2s) | First request slow after idle | Provisioned concurrency ($$$) |
| 10GB max memory | Can't run memory-heavy ML models | Use ECS/EC2 for those |
| 6MB payload (sync) | Can't return large files directly | Return S3 pre-signed URL instead |
| Stateless | No local disk between invocations | Use DynamoDB/S3/ElastiCache for state |
| Vendor lock-in | Lambda code tied to AWS event model | Accept it or use containers |
| Cold start + VPC | VPC Lambda cold start adds 1-5 seconds | Only use VPC if Lambda needs private resources |
| Debugging harder | No SSH, no "tail logs" live | X-Ray + structured logging + local testing (SAM) |

---

## 10. Interview Talking Points

### 2-Minute Version

"Built an event-driven image processing pipeline using serverless on AWS. API Gateway handles REST requests with Cognito authentication, Lambda processes business logic, DynamoDB stores metadata. When users upload to S3, EventBridge triggers processing Lambdas — resize, generate thumbnails, create reports. SQS decouples services for reliability (DLQ catches failures), SNS fans out notifications. Full pipeline costs $17/month for 1M requests versus $115/month if we'd used EKS. X-Ray provides distributed tracing across all Lambda invocations. Key decision: serverless for variable/event-driven workloads, containers for steady-state services. Right tool for the job."

### Key Interview Q&A

**Q: "Why not just use containers for everything?"**  
A: Containers make sense for steady, long-running services. But for event-driven tasks (file upload → process, API with variable traffic, cron jobs), serverless is cheaper, faster to deploy, and zero ops. We use both — containers for core services, serverless for glue and events.

**Q: "How do you handle Lambda cold starts?"**  
A: Three approaches. (1) Keep functions small (fast init). (2) Provisioned concurrency for latency-critical paths ($$$). (3) Warm-up scheduled event every 5 min for critical functions. For most APIs, 200ms cold start is acceptable — users don't notice.

**Q: "What happens if Lambda fails?"**  
A: DLQ (Dead Letter Queue). Failed event goes to SQS DLQ after 3 retries. CloudWatch alarm on DLQ message count. We investigate, fix, replay messages from DLQ. Data is never lost.

**Q: "How do you test serverless locally?"**  
A: AWS SAM CLI — `sam local invoke` runs Lambda in Docker locally with real event payloads. `sam local start-api` simulates full API Gateway. Integration tests hit staging with real AWS services.
