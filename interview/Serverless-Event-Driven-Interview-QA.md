# Interview Q&A Bank: Serverless Event-Driven Architecture

## Project: Automated Security Remediation Engine — Self-Healing Infrastructure

**Technologies:** AWS Lambda, EventBridge, SQS, SNS, DynamoDB, API Gateway, Step Functions, AWS Config, S3, X-Ray, SAM

---

## Section 1: Project Story

### Q1: Walk me through this project in 2 minutes.

**Answer:**
Built a serverless security remediation engine that auto-fixes AWS Config violations in real-time. AWS Config detects violations (open security groups, public S3 buckets, unencrypted EBS), EventBridge routes events based on pattern matching to SQS queues for reliable buffering, Lambda functions remediate within 90 seconds — zero human intervention. Every action logged to DynamoDB as audit trail, SNS fans out notifications to Slack and PagerDuty. Weekly compliance reports generated via scheduled Lambda, stored in S3. Dashboard API via API Gateway lets security team query remediation history. Entire system costs $0.07/month because serverless charges per-execution. This directly supports our Landing Zone (Project 4) — SCPs prevent violations, this engine fixes ones that slip through. Defence in depth.

---

### Q2: Why serverless instead of a container service for this?

**Answer:**
- **Events are sporadic:** 5-50 security violations per day. Each takes 2 seconds to fix.
- **Math:** Container running 24/7 to handle 5 events = $75/month idle. Lambda runs 2 seconds per event = $0.07/month total.
- **Zero ops:** No patching Lambda. No scaling config. No on-call for the automation platform itself.
- **Instant scale:** If a misconfigured Terraform module creates 500 bad security groups at once, Lambda scales to 500 concurrent executions instantly. Container would queue for hours.
- **When I'd use containers instead:** If events were constant (1000+/minute) and needed sub-10ms latency. Our use case is perfect for serverless — sporadic, short-lived, variable.

---

## Section 2: Technical Deep-Dive

### Q3: Explain the complete event flow from violation to remediation.

**Answer:**
```
1. Someone opens SSH to 0.0.0.0/0 on a Security Group
2. AWS Config evaluates rule "restricted-ssh" → marks sg-123 as NON_COMPLIANT (within 1 min)
3. Config publishes event to EventBridge default bus
4. EventBridge rule matches: source=aws.config, configRuleName=restricted-ssh
5. EventBridge delivers event to SQS queue "sg-remediation-queue"
6. Lambda polls SQS → receives message → reads sg-123 from event body
7. Lambda calls ec2:RevokeSecurityGroupIngress → removes 0.0.0.0/0 rule
8. Lambda writes audit record to DynamoDB (timestamp, resource, action, status)
9. Lambda publishes to SNS topic → Slack gets "🔒 Fixed: sg-123 had SSH open"
10. Total time: ~90 seconds. Cost: $0.0000002.
```

---

### Q4: Why is SQS between EventBridge and Lambda? Why not trigger Lambda directly?

**Answer:**
| | Direct trigger (EventBridge → Lambda) | With SQS (EventBridge → SQS → Lambda) |
|---|---|---|
| Lambda fails | Event LOST forever | Message stays in queue, retries 3 times |
| 100 events at once | 100 concurrent Lambdas (could hit concurrency limit) | Queue buffers, Lambda processes at its pace |
| Debugging | No trace of failed events | DLQ holds failed messages for investigation |
| Replay | Can't replay | Re-drive messages from DLQ |

**Bottom line:** SQS adds reliability. For a security remediation engine, we can NEVER lose an event. One missed violation = potential breach.

---

### Q5: How does the Dead Letter Queue (DLQ) work and why is it critical?

**Answer:**
```
Normal flow:  SQS → Lambda processes → success → message deleted
Failure flow: SQS → Lambda fails → message becomes visible again (retry)
              → Lambda fails again (retry 2)
              → Lambda fails THIRD time → message moves to DLQ
              → CloudWatch alarm: "DLQ has messages!" → PagerDuty pages team
```

**Why critical:** DLQ means "something is broken that automation can't fix." Could be:
- AWS API throttling (need to request limit increase)
- Bug in Lambda code (edge case not handled)
- Permission issue (IAM role missing a new permission)

**We WANT this to page us** — it means a security violation EXISTS and ISN'T being fixed. That's worse than a false alert.

---

### Q6: How does the scheduled compliance report work?

**Answer:**
- **EventBridge Schedule rule:** `rate(7 days)` — fires every Monday 9 AM UTC.
- **Target:** Lambda `weekly-compliance-report`.
- **Lambda logic:**
  1. Query DynamoDB: all remediations in last 7 days (using GSI on timestamp).
  2. Query AWS Config: current compliance status across all rules.
  3. Generate HTML report (violations found, auto-fixed, still pending, DLQ items).
  4. Upload to S3: `s3://reports/compliance/2026-07-22.html`
  5. Publish to SNS: "Weekly report ready: 23 fixed, 0 pending, 0 in DLQ."

**Cost of running once per week:** $0.000001. Literally free.

---

### Q7: How do you secure the Lambda functions themselves?

**Answer:**
| Security Control | How |
|---|---|
| IAM least privilege | sg-remediation Lambda can ONLY call `ec2:RevokeSecurityGroupIngress` — nothing else |
| No VPC | Lambda doesn't need private network access → avoids cold start penalty + simpler |
| Secrets | Slack webhook URL in Secrets Manager (not env var — env vars visible in console) |
| Concurrency limit | Reserved concurrency = 10 (prevents runaway execution from a bug) |
| Encryption | SQS: SSE-SQS. DynamoDB: SSE-KMS. S3: SSE-S3 |
| Logging | Every invocation auto-logged to CloudWatch (can't disable) |
| X-Ray tracing | Enabled — shows full event path with timing |

**Why concurrency limit = 10?** Safety valve. If our Lambda has a bug and starts deleting ALL security group rules (not just bad ones), it can only run 10 at a time. We'd catch it from DLQ alarm before it does 11th.

---

## Section 3: Troubleshooting

### Q8: Lambda is being invoked but DynamoDB audit records aren't being written. What's wrong?

**Answer:**
1. **Check CloudWatch Logs:** Is Lambda completing successfully or erroring?
2. **Common causes:**
   - IAM role missing `dynamodb:PutItem` permission (permission was removed or policy changed).
   - Wrong table name in Lambda code (typo, or different table in staging vs prod).
   - DynamoDB throttling (exceeded provisioned capacity — switch to on-demand mode).
   - Lambda timeout too short — DynamoDB write happens at the end, Lambda times out before reaching it.
3. **Debug:** Add structured logging BEFORE and AFTER the DynamoDB call. Check if Lambda reaches that line.
4. **Quick fix:** Check IAM role → verify DynamoDB permissions. 90% of the time it's a permission issue after someone "cleaned up" policies.

---

### Q9: EventBridge rule exists but events aren't reaching SQS. How do you debug?

**Answer:**
1. **Verify event is being published:** CloudTrail → filter by `PutEvents` or check AWS Config → is the rule actually evaluating? (might be disabled).
2. **Check EventBridge rule:** Is pattern correct? Common mistake: `detail-type` vs `detail.type` — one character off = no match.
3. **Test with Event Pattern Tester:** EventBridge console → "Rule" → "Test event pattern" → paste a sample event → does it match?
4. **Check SQS permissions:** SQS queue needs a resource policy allowing EventBridge to send messages to it.
5. **CloudWatch Metrics:** EventBridge publishes `MatchedEvents` and `FailedInvocations` metrics. If MatchedEvents=0 → rule isn't matching. If FailedInvocations>0 → target (SQS) is rejecting.

**Most common cause:** SQS resource policy doesn't allow `events.amazonaws.com` to `sqs:SendMessage`.

---

### Q10: Config rule shows NON_COMPLIANT resources but no remediation is happening. Full pipeline debug.

**Answer:**
Layer-by-layer check:
1. **Config → EventBridge:** Does Config publish to EventBridge? Check: is the Config rule in "Detective" mode (reports only) vs "Remediation" mode? We use Detective + our own Lambda (not Config's built-in remediation). Verify EventBridge `MatchedEvents` metric > 0.
2. **EventBridge → SQS:** Check SQS metric `NumberOfMessagesSent`. If 0 → EventBridge rule not matching (see Q9).
3. **SQS → Lambda:** Check SQS metric `NumberOfMessagesReceived` by Lambda. If 0 → Lambda trigger not configured (event source mapping missing or disabled).
4. **Lambda execution:** Check CloudWatch Logs → is Lambda running? Any errors?
5. **Lambda → EC2 API:** Is the remediation call succeeding? Check for `AccessDenied` in logs.

**One-liner debug:** `SQS ApproximateNumberOfMessagesVisible > 0` = messages stuck = Lambda not consuming = check Lambda event source mapping.

---

## Section 4: System Design

### Q11: How would you extend this to cover 100 different Config rules across 15 accounts?

**Answer:**
**Current:** One rule (restricted-ssh) → one Lambda.
**Scaled architecture:**

```
15 accounts (all send events to central Security account via EventBridge cross-account)
    │
    ▼
Central EventBridge (Security Account) — one bus, many rules:
    ├── Rule: sg-* violations → SQS-sg → Lambda-sg-remediation
    ├── Rule: s3-* violations → SQS-s3 → Lambda-s3-remediation
    ├── Rule: ebs-* violations → SQS-ebs → Lambda-ebs-remediation
    ├── Rule: rds-* violations → SQS-rds → Lambda-rds-remediation
    └── Rule: iam-* violations → SQS-iam → Lambda-iam-remediation (with extra approval)
```

**Key design decisions:**
- Cross-account EventBridge: All 15 accounts forward events to central security account bus.
- Separate queue per violation TYPE: Different blast radius, different IAM permissions.
- IAM-related remediations need human approval (too dangerous to auto-fix) → route to Step Functions with approval step.
- Same DynamoDB audit table, same SNS topic (centralized visibility).

---

### Q12: Design the Step Functions workflow for a complex remediation that needs approval.

**Answer:**
**Use case:** IAM policy violation (overly permissive `*` policy). Too dangerous to auto-fix — might break production.

```
Step 1: Detect (Config event arrives)
    ▼
Step 2: Analyze (Lambda: what's the impact? Which services use this role?)
    ▼
Step 3: Notify + Wait for Approval (SNS → Slack with "Approve/Deny" buttons → callback URL)
    ├── Approved → Step 4
    └── Denied → Log reason → End
    ▼
Step 4: Remediate (Lambda: replace `*` with specific permissions based on CloudTrail analysis)
    ▼
Step 5: Verify (Lambda: test that services still work with reduced permissions)
    ├── Pass → Step 6
    └── Fail → Rollback (restore original policy) → Alert
    ▼
Step 6: Log + Notify (DynamoDB + Slack: "IAM policy fixed for role X")
```

**Why Step Functions, not one Lambda?** Multi-step with human approval + wait state (could wait hours for approval). Lambda max is 15 min. Step Functions can wait up to 1 year.

---

## Section 5: Comparison & Decisions

### Q13: EventBridge vs direct Lambda trigger vs SNS — when do you use each?

**Answer:**
| Pattern | Use When | Example |
|---|---|---|
| **EventBridge → Target** | Pattern matching needed, multiple sources, decoupled | Config events routed to different Lambdas by rule type |
| **Direct Lambda invoke** | Simple 1:1 trigger, synchronous response needed | API Gateway → Lambda (user waits for response) |
| **SNS → Lambda** | Fan-out (one event, many consumers) | Notification: same message → Slack + Email + PagerDuty |
| **SQS → Lambda** | Reliability needed (retry, DLQ, backpressure) | Remediation queue — can't lose events |

**Our architecture uses ALL of them:** EventBridge (routing) → SQS (reliability) → Lambda (processing) → SNS (notification). Each serves a different purpose.

---

### Q14: DynamoDB vs RDS for the audit trail — why DynamoDB?

**Answer:**
| | DynamoDB (Our Choice) | RDS PostgreSQL |
|---|---|---|
| Server management | Zero (serverless) | Must manage instance, backups, patching |
| Scaling | Auto (handles 10 or 10,000 writes/day) | Must resize instance for more load |
| Idle cost | $0 (on-demand mode, pay per request) | ~$15/month minimum (instance always running) |
| Query pattern | Simple: get by event_id, query by timestamp range | Complex joins not needed here |
| Latency | Single-digit ms | Single-digit ms (same) |

**When RDS would be better:** If we needed complex queries (JOIN remediation data with account metadata with cost data) or if this was part of a larger application with existing RDS. For simple key-value audit logs, DynamoDB is perfect and cheaper.

---

### Q15: AWS Config auto-remediation vs our custom Lambda — why custom?

**Answer:**
AWS Config has built-in "remediation actions" (SSM Automation documents). Why did we build our own?

| | Config Built-in Remediation | Our Custom Lambda |
|---|---|---|
| Audit trail | Config logs it (basic) | DynamoDB with full context (who caused it, which team, related events) |
| Notifications | None built-in | SNS → Slack + PagerDuty (customizable) |
| Complex logic | Limited (SSM docs are rigid) | Full Python — can check conditions, skip false positives |
| Cross-account | One account at a time | Central Lambda remediates across 15 accounts |
| DLQ / retry | Basic retry | SQS with DLQ + alerting |
| Dashboard | Config console only | Custom API + DynamoDB (any UI can consume) |

**Key reason:** We needed centralized remediation across 15 accounts with custom notifications and audit trail. Config's built-in remediation is per-account, per-rule, with limited customization.

---

## Section 6: Behavioral

### Q16: How did you convince the security team to trust automated remediation?

**Answer (STAR):**
- **Situation:** Security team worried: "What if Lambda removes a legitimate rule and breaks production?"
- **Task:** Build trust in automation without removing human oversight.
- **Action:** Phased approach:
  1. **Week 1-2:** Lambda only LOGS violations (no auto-fix). Team sees: "We would have fixed 47 violations this week."
  2. **Week 3-4:** Lambda fixes + notifies. Team reviews every fix in Slack. Zero false positives confirmed.
  3. **Week 5+:** Full auto-remediation. DLQ as safety net. Team trusts the system.
  Also added: concurrency limit (max 10 simultaneous) + kill switch (disable Lambda trigger in 1 click).
- **Result:** After 2 months, security team asked: "Can we add more rules?" Trust earned through transparency and gradual rollout.

---

### Q17: What was the hardest bug you encountered in this project?

**Answer (STAR):**
- **Situation:** Lambda was successfully remediating, but the SAME security group was getting remediated every 5 minutes (infinite loop).
- **Task:** Figure out why the same event kept firing.
- **Action:** Root cause: Config re-evaluates every 5 minutes. Lambda removes bad rule → Config says "COMPLIANT." But then another automation (Terraform in the pipeline) re-applies the bad rule (it was in the Terraform code!) → Config says "NON_COMPLIANT" again → Lambda remediates again → loop.
- **Fix:** Added deduplication in DynamoDB — if same resource was remediated in last 30 minutes, skip and alert instead: "sg-123 keeps getting violated — investigate the SOURCE, not the symptom." Led us to fix the bad Terraform code.
- **Result:** Prevented infinite remediation loops. Added this pattern to all Lambda functions: "If same resource remediated > 2 times in 1 hour → stop and page human."

---

## Section 7: Future & Improvements

### Q18: What would you add next?

**Answer:**
| Priority | Improvement | Why |
|---|---|---|
| 1 | Cross-account EventBridge | All 15 accounts send events to central security account (currently per-account) |
| 2 | Approval workflow for risky remediations | IAM/networking changes too dangerous to auto-fix → Step Functions + human approval |
| 3 | Compliance dashboard (Grafana) | Visual trend: violations/week, MTTR, most common violation types |
| 4 | Terraform integration | When violation found, auto-create PR to fix the Terraform code (fix the SOURCE) |
| 5 | ML-based false positive detection | After 6 months of data, ML model identifies patterns that are always false positives → auto-suppress |

---

### Q19: How would this change if you needed sub-second response (real-time blocking, not remediation)?

**Answer:**
Current architecture: Detect → remediate in ~90 seconds. Fine for security groups (damage limited in 90s).

**For sub-second (e.g., block malicious API calls in real-time):**
- Can't use Config (evaluates every 1-5 min) → use CloudTrail real-time events or VPC Flow Logs.
- Can't use SQS (adds latency) → use EventBridge direct to Lambda.
- Can't afford cold starts → use Provisioned Concurrency ($$$) or move to container (always warm).
- Consider: AWS WAF + Lambda@Edge for HTTP-level blocking (sub-ms response at edge).

**Key insight:** Serverless is great for "fix within minutes." For "block within milliseconds," use different tools (WAF, NACLs, Security Groups — they're instant).

---

### Q20: If this project's events grew from 50/day to 50,000/day, what changes?

**Answer:**
| Component | At 50/day | At 50,000/day | Change Needed |
|---|---|---|---|
| Lambda concurrency | Default (10 reserved) | Increase to 100-500 | Request limit increase |
| SQS | Standard queue (fine) | Still fine (unlimited throughput) | No change |
| DynamoDB | On-demand ($0.01/mo) | On-demand (~$10/mo) or provisioned | Monitor, maybe switch to provisioned for cost |
| EventBridge | Free (< 1M events) | Still free tier | No change |
| Lambda cost | $0.07/mo | ~$70/mo | Still 10x cheaper than container ($750) |
| Architecture | Single Lambda per type | Consider batching (SQS batch size 10) | Lambda processes 10 messages per invocation |

**Bottom line:** Serverless scales without architectural changes until ~100K/day. Beyond that, consider: batch processing, DynamoDB provisioned mode, and potentially moving hot-path to containers for cost efficiency.

---

*End of Q&A Bank — 20 questions covering all 7 dimensions*
