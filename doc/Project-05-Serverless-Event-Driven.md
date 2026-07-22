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

### What We Built: Serverless Operations Automation Platform

**How this connects to Projects 1-4:**

| Event Source | From Which Project | What Happens |
|---|---|---|
| Security Group violation | Project 2 (3-Tier AWS) & Project 4 (Landing Zone) | Lambda auto-remediates (removes bad rule) |
| CI/CD deploy event | Project 1 (DevSecOps Pipeline) | Lambda creates Jira ticket on failure, notifies Slack |
| EKS node unhealthy | Project 3 (Kubernetes) | Lambda cordons node, pages on-call |
| Cost threshold exceeded | Project 2 (3-Tier AWS) | Lambda generates report, tags resources, alerts team lead |
| New account requested | Project 4 (Landing Zone) | Step Functions runs account vending workflow |
| S3 bucket made public | Project 4 (Landing Zone SCPs missed edge case) | Lambda removes public access instantly |
| SSL cert expiring < 14 days | Project 2 (3-Tier) & Project 3 (EKS Ingress) | Lambda creates renewal ticket |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  EVENT SOURCES (from Projects 1-4)                                               │
│                                                                                 │
│  Project 1 (CI/CD)──→ Jenkins Webhook ──→ API Gateway                          │
│  Project 2 (3-Tier)──→ AWS Config Rule ──→ EventBridge                         │
│  Project 3 (EKS)────→ CloudWatch Alarm ──→ EventBridge                         │
│  Project 4 (Landing)─→ GuardDuty Finding─→ EventBridge                         │
│                        AWS Budgets ──────→ SNS                                   │
│                        Scheduled (daily)─→ EventBridge (cron)                   │
└────────────────────────────────┬────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  EVENT ROUTING (EventBridge — the Air Traffic Controller)                        │
│                                                                                 │
│  Rule: source=aws.config, detail-type=ConfigRuleViolation ──→ Lambda-Remediate  │
│  Rule: source=aws.health, detail=EKS ──────────────────────→ Lambda-K8sOps     │
│  Rule: source=custom.cicd, detail=deploy-failed ───────────→ Lambda-Notify     │
│  Rule: schedule(rate=1 day) ───────────────────────────────→ Lambda-CertCheck  │
│  Rule: source=aws.guardduty ───────────────────────────────→ Lambda-Security   │
└────────────────────────────────┬────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PROCESSING (Lambda Functions — the Workers)                                     │
│                                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐             │
│  │ Lambda:           │  │ Lambda:           │  │ Lambda:           │             │
│  │ auto-remediate    │  │ cert-checker      │  │ cost-reporter     │             │
│  │                   │  │                   │  │                   │             │
│  │ • Remove bad SG   │  │ • Scan ACM certs  │  │ • Query Cost Exp  │             │
│  │ • Block public S3 │  │ • Check custom    │  │ • Tag untagged    │             │
│  │ • Fix IAM issues  │  │   certs on EC2/K8s│  │ • Generate report │             │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘             │
│           │                      │                      │                       │
│  ┌────────▼─────────┐  ┌────────▼─────────┐  ┌────────▼─────────┐             │
│  │ Lambda:           │  │ Lambda:           │  │ Step Functions:   │             │
│  │ k8s-ops           │  │ deploy-notifier   │  │ account-vending   │             │
│  │                   │  │                   │  │                   │             │
│  │ • Cordon node     │  │ • Parse event     │  │ • Create account  │             │
│  │ • Scale node group│  │ • Create Jira     │  │ • Apply baseline  │             │
│  │ • Restart pod     │  │ • Notify Slack    │  │ • Setup networking│             │
│  └────────┬─────────┘  └────────┬─────────┘  │ • Configure SSO   │             │
│           │                      │             │ • Notify team      │             │
│           │                      │             └────────┬─────────┘             │
└───────────┼──────────────────────┼──────────────────────┼───────────────────────┘
            │                      │                      │
            ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STORAGE & NOTIFICATIONS                                                         │
│                                                                                 │
│  DynamoDB (audit trail — every action logged with timestamp)                    │
│  S3 (reports — cost reports, compliance reports, cert status)                   │
│  Slack (real-time team notifications — #ops-automation channel)                 │
│  PagerDuty (P1 alerts — only on critical: node down, security breach)          │
│  Jira (auto-created tickets — deploy failures, cert renewals)                  │
│  Email (weekly summary — cost report to team leads)                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Why Serverless for This? (Not Containers)

| Reason | Explanation |
|---|---|
| Variable traffic | Security events happen 0-50 times/day. Paying for a container 24/7 to handle 5 events = wasteful |
| Event-driven by nature | React to events, not serve constant requests |
| Short execution | Each remediation takes 2-10 seconds (well under 15 min limit) |
| Zero ops | No patching Lambda. Focus on the automation logic, not infrastructure |
| Cost | ~$5-10/month for all functions vs ~$150/month for an ECS service doing the same |
| Scale to zero | Weekends/nights = zero events = $0 cost |

---

## 4a. Detailed Use Cases (How Each Lambda Works)

### Use Case 1: Auto-Remediate Security Group Violation (Project 2 & 4)

**Trigger:** AWS Config rule detects SG with port 22 open to 0.0.0.0/0

```
AWS Config Rule fires → EventBridge → Lambda (auto-remediate)
```

```python
# lambda_function.py — Security Group auto-remediation
import boto3
import json

ec2 = boto3.client('ec2')
dynamodb = boto3.resource('dynamodb')
audit_table = dynamodb.Table('ops-automation-audit')

def handler(event, context):
    # Extract violation details from Config event
    sg_id = event['detail']['resourceId']
    
    # Remove the offending rule
    ec2.revoke_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        }]
    )
    
    # Log to DynamoDB (audit trail)
    audit_table.put_item(Item={
        'event_id': context.aws_request_id,
        'timestamp': event['time'],
        'action': 'REMEDIATE_SG',
        'resource': sg_id,
        'detail': 'Removed SSH 0.0.0.0/0 rule',
        'status': 'SUCCESS'
    })
    
    # Notify Slack
    notify_slack(f"🔒 Auto-remediated: SG {sg_id} had port 22 open to world. Rule removed.")
    
    return {'statusCode': 200, 'body': f'Remediated {sg_id}'}
```

**Result:** Within 30 seconds of someone opening SSH to the world, Lambda removes it automatically. No human needed. Full audit trail in DynamoDB.

---

### Use Case 2: CI/CD Deploy Failure Notification (Project 1)

**Trigger:** Jenkins webhook on deploy failure → API Gateway → Lambda

```python
# lambda_function.py — Deploy failure handler
def handler(event, context):
    body = json.loads(event['body'])
    
    job_name = body['job_name']       # e.g., "learneasyai-prod-deploy"
    build_number = body['build_number']
    status = body['status']            # "FAILURE"
    commit_sha = body['commit_sha']
    author = body['author']
    
    if status == 'FAILURE':
        # Create Jira ticket
        jira_ticket = create_jira_ticket(
            summary=f"Deploy Failed: {job_name} #{build_number}",
            description=f"Commit: {commit_sha}\nAuthor: {author}\nLogs: {body['build_url']}",
            priority="High"
        )
        
        # Notify Slack with context
        notify_slack(
            channel="#deployments",
            message=f"❌ Deploy FAILED: {job_name} #{build_number}\n"
                    f"Author: {author}\n"
                    f"Jira: {jira_ticket}\n"
                    f"Logs: {body['build_url']}"
        )
        
        # Log to DynamoDB
        log_audit('DEPLOY_FAILURE', job_name, build_number)
    
    return {'statusCode': 200}
```

---

### Use Case 3: EKS Node Unhealthy (Project 3)

**Trigger:** CloudWatch Alarm (EKS node NotReady > 5 min) → EventBridge → Lambda

```python
# lambda_function.py — K8s node operations
import boto3
from kubernetes import client, config

def handler(event, context):
    node_name = event['detail']['dimensions']['NodeName']
    cluster_name = event['detail']['dimensions']['ClusterName']
    
    # Get EKS credentials
    eks = boto3.client('eks')
    cluster_info = eks.describe_cluster(name=cluster_name)
    
    # Connect to K8s API
    # (Uses IRSA — Lambda has IAM role with EKS access)
    k8s_client = get_k8s_client(cluster_info)
    
    # Cordon the node (prevent new pods)
    body = {"spec": {"unschedulable": True}}
    k8s_client.patch_node(node_name, body)
    
    # Page on-call (P1 — node is down)
    trigger_pagerduty(
        severity="critical",
        summary=f"EKS node {node_name} in {cluster_name} is NotReady. Auto-cordoned.",
        details=f"Node has been cordoned. Investigate and drain if needed."
    )
    
    # Log action
    log_audit('NODE_CORDONED', node_name, cluster_name)
    
    return {'statusCode': 200}
```

---

### Use Case 4: SSL Certificate Expiry Check (Projects 2 & 3)

**Trigger:** EventBridge scheduled rule (runs daily at 9 AM)

```python
# lambda_function.py — Certificate expiry scanner
import boto3
from datetime import datetime, timedelta

acm = boto3.client('acm')
WARNING_DAYS = 30
CRITICAL_DAYS = 14

def handler(event, context):
    # Scan all ACM certificates
    certs = acm.list_certificates()['CertificateSummaryList']
    expiring_soon = []
    
    for cert in certs:
        detail = acm.describe_certificate(CertificateArn=cert['CertificateArn'])
        expiry = detail['Certificate']['NotAfter']
        days_left = (expiry - datetime.now(expiry.tzinfo)).days
        
        if days_left <= CRITICAL_DAYS:
            expiring_soon.append({'cert': cert['DomainName'], 'days': days_left, 'severity': 'CRITICAL'})
        elif days_left <= WARNING_DAYS:
            expiring_soon.append({'cert': cert['DomainName'], 'days': days_left, 'severity': 'WARNING'})
    
    if expiring_soon:
        for cert_info in expiring_soon:
            # Create Jira ticket for renewal
            create_jira_ticket(
                summary=f"SSL Cert Expiring: {cert_info['cert']} ({cert_info['days']} days)",
                priority="Critical" if cert_info['severity'] == 'CRITICAL' else "High"
            )
        
        # Slack summary
        notify_slack(f"🔐 Certificate Report: {len(expiring_soon)} certs expiring within {WARNING_DAYS} days")
    
    # Store report in S3
    save_report_to_s3(expiring_soon)
    
    return {'statusCode': 200, 'expiring': len(expiring_soon)}
```

---

### Use Case 5: Account Vending (Project 4 — Step Functions)

**Trigger:** ServiceNow approval webhook → API Gateway → Step Functions

```
Step 1: Create AWS Account (Organizations API)
    │ Wait 60s (account activation)
    ▼
Step 2: Move to correct OU (SCPs auto-apply)
    │
    ▼
Step 3: Apply baseline (Terraform via CodeBuild)
    │ - VPC, CloudTrail, GuardDuty, Config
    ▼
Step 4: Configure SSO permission sets
    │
    ▼
Step 5: Notify team (Slack + Email)
    │
    ▼
Step 6: Update DynamoDB (account registry)
    │
    ▼
Step 7: Close ServiceNow ticket (API call)
```

**Why Step Functions (not single Lambda)?** Account vending takes 10-15 minutes total (waiting for account activation, Terraform apply, health checks). Single Lambda has 15 min max. Step Functions can run for up to 1 year, with retries per step and visual debugging.

---

### Use Case 6: Cost Alert & Auto-Tagging (Project 2)

**Trigger:** AWS Budget threshold exceeded → SNS → Lambda

```python
def handler(event, context):
    budget_name = event['Records'][0]['Sns']['Message']  # Parse SNS
    
    # Find untagged resources (likely cause of unexpected cost)
    untagged = find_untagged_resources()
    
    # Auto-tag with "NeedsOwner" 
    for resource in untagged:
        tag_resource(resource['arn'], {'CostCenter': 'UNASSIGNED', 'NeedsOwner': 'true'})
    
    # Generate cost breakdown report
    report = generate_cost_report_by_service()
    save_to_s3(report, f"cost-reports/{today}.html")
    
    # Notify team lead with report link
    notify_slack(
        channel="#finops",
        message=f"💰 Budget alert: {budget_name} exceeded threshold.\n"
                f"Found {len(untagged)} untagged resources (auto-tagged).\n"
                f"Report: https://s3.../cost-reports/{today}.html"
    )
    
    return {'statusCode': 200}

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

"Built a serverless operations automation platform that supports all our other infrastructure projects. EventBridge routes events from AWS Config (security violations), CloudWatch (EKS node health), Jenkins webhooks (deploy failures), and AWS Budgets (cost alerts) to purpose-built Lambda functions. Each Lambda performs a specific action: auto-remediate open security groups, cordon unhealthy K8s nodes, create Jira tickets on deploy failures, scan certificates for expiry, and auto-tag untagged resources for cost attribution. Account vending uses Step Functions to orchestrate the 7-step workflow (create account → apply baseline → configure SSO → notify). Everything logged to DynamoDB as audit trail, reports stored in S3, notifications via Slack/PagerDuty/Email. Costs $10/month total — versus $150/month if we ran this as a container service. Key design: serverless is perfect for event-driven operations automation where events are sporadic and short-lived."

### How This Connects to Other Projects

```
Project 4 (Landing Zone) ──→ Account vending (Step Functions)
                          ──→ SCP violation remediation (Lambda)
Project 2 (3-Tier AWS)   ──→ SG auto-remediation (Lambda)
                          ──→ Cost alerts + tagging (Lambda)
                          ──→ Cert expiry scanning (Lambda)
Project 3 (EKS/K8s)      ──→ Node health automation (Lambda)
                          ──→ Pod restart alerting (Lambda)
Project 1 (CI/CD)         ──→ Deploy failure ticketing (Lambda)
                          ──→ Pipeline status dashboard (API GW + DynamoDB)
```

**One-liner for interview:** "This serverless platform is the glue that makes my other projects self-healing and observable. It's the automated operations layer that reacts to events across the entire infrastructure."

### Key Interview Q&A

**Q: "Why serverless for this and not a container service?"**  
A: Events are sporadic (5-50/day). A container running 24/7 to handle 5 events = $150/month wasted. Lambda runs for 2-10 seconds per event, costs $0.0001 per execution. Total monthly cost: ~$10. Also zero ops — no patching, no scaling, no on-call for the automation platform itself.

**Q: "What if Lambda fails to remediate?"**  
A: Three safety nets. (1) DLQ — failed event goes to dead letter queue after 3 retries. (2) CloudWatch alarm on DLQ depth > 0 → alerts team. (3) All actions logged to DynamoDB — we can replay or investigate. Plus, AWS Config will re-fire the event if the violation persists (self-correcting).

**Q: "How do you test this?"**  
A: SAM CLI locally (`sam local invoke` with sample EventBridge events). Integration tests in staging account that intentionally create violations → verify Lambda remediates within 60 seconds → verify DynamoDB audit record → verify Slack notification received.

**Q: "Why EventBridge over direct Lambda triggers?"**  
A: Decoupling. Config doesn't know which Lambda handles it — EventBridge routes based on rules. If we add a new automation (e.g., auto-fix unencrypted EBS), we add a new rule + Lambda — zero changes to existing code. Also: one event can trigger multiple targets (remediate AND notify AND log).

**Q: "Why Step Functions for account vending instead of one Lambda?"**  
A: Account creation takes 10-15 minutes (waiting for AWS to activate the account, running Terraform, health checks). Single Lambda max is 15 min — too risky. Step Functions handles: retries per step, visual debugging (see exactly which step failed), wait states (pause for account activation), and parallel execution (SSO + networking in parallel).
