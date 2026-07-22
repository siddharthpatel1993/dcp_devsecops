# Interview Q&A Bank: Multi-Account AWS Landing Zone

## Project: Managing 15+ AWS Accounts with Governance, SCPs, SSO & OIDC

**Technologies:** AWS Organizations, SCPs, IAM Identity Center (SSO), OIDC Federation, GuardDuty, Security Hub, CloudTrail, Terraform, Control Tower

---

## Section 1: Project Story

### Q1: Walk me through this project in 2 minutes.

**Answer:**
Architected a 15-account AWS Organization with proper OU structure — Security, Infrastructure, Production, Non-Production, and Sandbox. SCPs enforce guardrails that even admin can't bypass: no disabling logging, region restrictions, encryption required. IAM Identity Center provides SSO via corporate directory — no IAM users in any account. CI/CD uses OIDC federation with GitHub Actions — no long-lived keys, scoped to specific repo and branch. Centralized security: GuardDuty for threats, Config for compliance, CloudTrail immutable in log archive. Account vending delivers a fully baselined account in under 30 minutes. This is the foundation that my other projects (CI/CD pipeline, 3-Tier infra, EKS clusters) all run on top of.

---

### Q2: What business problem does this solve?

**Answer:**
- **Before:** 15 accounts created ad-hoc. No guardrails. Dev could delete prod resources. No audit trail. Cost attribution impossible. Security audit failed because no centralized logging.
- **After:** Every account born with security baseline (CloudTrail, GuardDuty, Config). SCPs prevent dangerous actions. Cost per team visible. Audit takes 30 minutes (not 2 weeks). New account ready in 30 minutes (not 2 weeks of tickets).
- **Impact:** Passed SOC2 audit first attempt. Reduced account provisioning from 2 weeks to 30 minutes. Zero security incidents from misconfigured accounts since implementation.

---

## Section 2: Technical Deep-Dive

### Q3: How do SCPs work? What can they do that IAM policies cannot?

**Answer:**
SCPs are **permission boundaries** applied at the Organization/OU/Account level. They LIMIT what anyone (including root/admin) can do.

**Key difference from IAM:**
- IAM policy: "User X CAN do Y." (grants access)
- SCP: "NOBODY in this account can do Z, regardless of their IAM permissions." (limits maximum possible permissions)

**Analogy:** IAM = your employee badge opens specific doors. SCP = building fire code says "this floor cannot have the emergency exit removed" — even if you're the building owner.

**Example:** SCP on Production OU:
```json
{
  "Effect": "Deny",
  "Action": ["ec2:RunInstances"],
  "Condition": {
    "StringNotEquals": { "aws:RequestedRegion": ["us-east-1", "eu-west-1"] }
  }
}
```
Nobody in any production account can launch EC2 outside approved regions — even with AdministratorAccess IAM policy.

---

### Q4: How does OIDC cross-account access work for CI/CD?

**Answer:**
1. GitHub Actions runs → GitHub generates a short-lived JWT token saying: "I am repo X, branch main, workflow deploy.yml"
2. Pipeline calls `sts:AssumeRoleWithWebIdentity` with this token
3. AWS IAM checks: "Do I trust GitHub's OIDC provider? Does the token match the trust policy conditions (specific repo + branch)?"
4. If yes → AWS returns temporary credentials (15 minutes)
5. Pipeline uses creds to deploy → credentials expire automatically

**Why not access keys?** Keys are permanent, work from anywhere, must be rotated manually. OIDC: no secrets stored, scoped to exact repo+branch, auto-expires, CloudTrail shows exactly which workflow used it.

---

### Q5: How is centralized logging architecture designed?

**Answer:**
```
All 15 accounts → Organization CloudTrail → S3 in Log Archive Account
                                              │
                                         SCP: Nobody can delete (not even admin)
                                         S3 Object Lock: WORM (Write Once Read Many)
                                         Lifecycle: Glacier after 90 days
                                         Retention: 7 years (compliance)
```

- **Organization Trail:** Single trail covers ALL accounts. No per-account setup needed.
- **Log Archive account:** Dedicated account in Security OU. Only security team has read access. SCPs prevent deletion of S3 bucket or disabling CloudTrail from ANY account.
- **Why separate account?** If attacker compromises a workload account, they can't delete the evidence. Logs are in a different account they don't have access to.

---

### Q6: How does Account Vending work?

**Answer:**
Team lead requests account → Approved → Automation triggers:

1. `aws organizations create-account` → new account in correct OU
2. Terraform applies baseline module: VPC, CloudTrail, GuardDuty, Config, IAM roles
3. Transit Gateway attachment (networking to shared services)
4. SSO permission sets assigned (dev team gets DeveloperAccess)
5. Budget alarm set ($500 default)
6. Slack notification: "Your account is ready"

**Time:** < 30 minutes (fully automated). Previously: 2 weeks (manual tickets, console clicking).

---

## Section 3: Troubleshooting

### Q7: SCP is blocking a legitimate action in production. How do you handle it?

**Answer:**
1. **Identify:** Check CloudTrail → find the denied API call → which SCP blocked it (`AccessDenied` with `ExplicitDeny` from organization policy).
2. **Evaluate:** Is the action genuinely needed? Or is there a safer alternative?
3. **Options:**
   - Add a condition to the SCP (allow this specific service role, deny everyone else)
   - Move the account to a different OU with less restrictive SCPs (temporary)
   - Create an SCP exception using condition keys (e.g., allow if `aws:PrincipalTag/team = "platform"`)
4. **Never:** Remove the SCP entirely. Fix with precision, not a sledgehammer.
5. **Document:** Update the SCP decision log — why this exception exists, when to review.

---

### Q8: GuardDuty shows "EC2 instance communicating with known C2 server." What's your response?

**Answer:**
1. **Severity:** CRITICAL. Potential compromised instance.
2. **Immediate:** Isolate the instance — change SG to deny ALL traffic (don't terminate — preserve forensic evidence).
3. **Investigate:** Which account? Which instance? What's running? Check CloudTrail for how attacker got in (credential leak? vulnerable app?).
4. **Contain:** Revoke any IAM credentials on that instance. Check if lateral movement occurred (other accounts, other instances).
5. **Notify:** Security team, incident channel, update ServiceNow incident ticket.
6. **Remediate:** Patch vulnerability, rotate all credentials that instance had access to.
7. **Post-incident:** Blameless retro. Add Config rule or SCP to prevent recurrence.

---

### Q9: A developer says "I can't deploy — OIDC role assumption fails." How do you debug?

**Answer:**
1. **Check GitHub Actions logs:** What error? "Not authorized to perform sts:AssumeRoleWithWebIdentity" or "WebIdentityErr"?
2. **Common causes:**
   - Wrong branch: Trust policy allows `ref:refs/heads/main` but dev is on `feature/xyz` branch.
   - Wrong repo: Trust policy condition has a typo in repo name.
   - OIDC provider thumbprint outdated (GitHub rotated their cert — rare but happens).
   - IAM role doesn't exist in the target account (Terraform not applied there yet).
3. **Debug command:** Check trust policy on the role → verify `Condition.StringEquals` matches EXACTLY what GitHub sends as the `sub` claim.
4. **Fix:** Update trust policy condition or ensure dev is deploying from the correct branch.

---

## Section 4: System Design

### Q10: Design a Landing Zone for a company growing from 5 to 50 teams.

**Answer:**
**Key changes from small (5 teams) to large (50 teams):**

1. **OU structure:** Add team-level sub-OUs under Workloads (not flat). `Workloads/TeamA-Prod`, `Workloads/TeamA-Dev`.
2. **Account vending:** Must be fully self-service (ServiceNow + API Gateway + Step Functions). 50 teams × manual = impossible.
3. **Networking:** Transit Gateway with route tables per environment (prod traffic can't route to dev). Shared VPC for cost optimization.
4. **Cost:** Kubecost/CUR reports per team OU. Budget alarms per account. Monthly chargeback reports.
5. **SCPs:** Layered — root level (everyone), environment level (prod stricter), team level (sandbox very restricted).
6. **SSO:** Permission sets per role (developer, lead, admin). Team → OU mapping automated via SCIM from corporate directory.
7. **Platform team:** Dedicated team owns the Landing Zone. Teams consume via self-service.

---

### Q11: How would you extend this to multi-region governance?

**Answer:**
- **SCPs:** Already region-restricted for prod (us-east-1, eu-west-1 only). Add approved regions as needed.
- **CloudTrail:** Organization trail covers all regions by default — no change needed.
- **GuardDuty:** Enable in all active regions (multi-region detector). Aggregate findings to Security Hub in one region.
- **Networking:** Transit Gateway per region + inter-region peering for approved traffic patterns.
- **Terraform:** Same modules with region parameter. State per region per account.
- **Data residency:** SCPs enforce data stays in approved regions (GDPR compliance — EU data in eu-west-1 only).

---

## Section 5: Comparison & Decisions

### Q12: Why custom Landing Zone with Terraform over AWS Control Tower?

**Answer:**
| | Control Tower | Custom (Our Choice) |
|---|---|---|
| Setup | Quick (wizard) | More work upfront (Terraform) |
| Customization | Limited (Account Factory defaults) | Unlimited (any baseline) |
| Networking | Basic (default VPC) | Full control (Transit Gateway, custom CIDRs) |
| SCPs | Pre-built guardrails | Custom to our compliance needs |
| Account factory | Built-in (limited customization) | Custom (Step Functions + Terraform) |
| Drift detection | Built-in | Custom (terraform plan + alerts) |

**Decision:** Control Tower is opinionated — doesn't fit when you need custom networking (Transit Gateway), non-standard OU structure, or organization-specific SCPs. We needed full control over every aspect.

**When Control Tower wins:** Greenfield, small company, standard requirements, wants to move fast with less engineering.

---

### Q13: SCP vs IAM Policy — when do you use which?

**Answer:**
| | SCP | IAM Policy |
|---|---|---|
| Scope | Everyone in account/OU (including root) | Specific user/role/group |
| Purpose | Maximum permission boundary ("nobody CAN") | Grant specific access ("this user CAN") |
| Override | Cannot be overridden by any IAM policy | Can be overridden by resource policies in some cases |
| Use case | Guardrails: prevent region misuse, disable logging, public S3 | Grant access: developer can deploy to this namespace |

**Rule of thumb:** SCP = "prevent dangerous things organization-wide." IAM = "grant specific people access to specific resources."

---

### Q14: Why OIDC over storing AWS access keys in GitHub Secrets?

**Answer:**
| | Access Keys | OIDC (Our Choice) |
|---|---|---|
| Stored where | GitHub Secrets (encrypted, but persistent) | Nowhere (generated on-the-fly) |
| Lifetime | Permanent (until you manually rotate) | 15 minutes (auto-expires) |
| If leaked | Permanent access until discovered + rotated | Useless within 15 minutes |
| Scope | Whoever has the key can use from anywhere | Only specific repo + specific branch |
| Audit | "key AKIA... was used" (who? which repo?) | "repo:org/app:ref:main used role X" (exact source) |
| Rotation | Manual (90-day reminders, often forgotten) | Automatic (new token every run) |

---

## Section 6: Behavioral & Leadership

### Q15: How did you get buy-in from teams who were happy with their existing accounts?

**Answer (STAR):**
- **Situation:** Teams had "their" accounts for 2 years. Worked fine (in their view). Didn't want "governance overhead."
- **Task:** Migrate to governed Landing Zone without alienating teams.
- **Action:** Started with the PAIN they felt: "Remember when dev accidentally deleted the prod S3 bucket? That can't happen with SCPs." Showed: "Your account doesn't change — we just add guardrails around it. Like adding seatbelts to a car you already drive." Migrated one willing team first as proof-of-concept.
- **Result:** First team migrated, zero disruption. They got SSO (no more 15 passwords), budget visibility (first time seeing their costs), and faster account creation for a new project. Other teams asked to join within 2 weeks.

**Learning:** Sell the benefits to THEM (SSO, cost visibility, faster accounts), not the benefits to YOU (governance, compliance).

---

### Q16: Tell me about a time an SCP caused a production incident.

**Answer (STAR):**
- **Situation:** Applied region-restriction SCP to Production OU. Forgot that one service used Lambda@Edge (which deploys to us-east-1 regardless of app region — CloudFront requirement).
- **Task:** Lambda@Edge deployment failed. CDN couldn't update. Users got stale content for 2 hours.
- **Action:** Identified SCP blocking us-east-1 for that specific service. Added condition: `"StringNotLike": {"aws:PrincipalArn": "arn:aws:iam::*:role/cloudfront-lambda-role"}` — allows only that role to deploy in us-east-1.
- **Result:** Fixed in 30 minutes. Added to runbook: "Before applying SCPs, check for services that require specific regions (Lambda@Edge, CloudFront, IAM, Route53 — all are global/us-east-1 only)."

**Learning:** SCPs are powerful but unforgiving. Always test in non-prod OU first. Keep an "SCP exception request" process.

---

## Section 7: Future & Improvements

### Q17: What would you add next to this Landing Zone?

**Answer:**
| Priority | Improvement | Why |
|---|---|---|
| 1 | AWS Config auto-remediation | Config detects violation → Lambda auto-fixes (not just alerts) |
| 2 | Service Catalog for self-service | Teams request pre-approved architectures (VPC, EKS, RDS) |
| 3 | Cost anomaly detection per account | Alert when spending deviates >20% from baseline |
| 4 | Terraform Cloud/Spacelift | Replace local state with collaborative IaC platform |
| 5 | PrivateLink for all shared services | Remove NAT Gateway dependency for cross-account communication |

---

### Q18: How does the Landing Zone evolve toward Platform Engineering?

**Answer:**
```
Current (Landing Zone):     Team requests account → Platform team provisions → Team deploys manually
Future (Platform):          Team fills form → Self-service portal provisions EVERYTHING → Deploy in 5 min
```

Evolution:
1. **Today:** Landing Zone provides accounts + guardrails. Teams still do manual infra work.
2. **Next:** Service Catalog provides "golden paths" — click to get VPC+EKS+RDS pre-configured.
3. **Future:** Backstage developer portal — single pane: create project → get account + cluster + pipeline + monitoring automatically. Developer never sees AWS console.

**Key shift:** From "here's your account, good luck" → "here's your production-ready environment, just deploy your code."

---

## Bonus: Cross-Cutting

### Q19: How do you ensure nobody bypasses the Landing Zone and creates accounts outside the Organization?

**Answer:**
1. **Billing alarm:** Any new account not in Organization → immediate alert (check consolidated billing).
2. **Root email control:** Only platform team has access to the email used for new AWS accounts.
3. **Corporate process:** AWS account creation requires procurement approval (credit card/PO controlled by finance).
4. **Education:** Teams know they get a baselined account in 30 minutes — no incentive to go rogue.
5. **Audit:** Quarterly check — any accounts with company email not in Organization? Investigate.

---

### Q20: How do you handle the "break glass" scenario — engineer needs emergency access to prod at 3 AM?

**Answer:**
- **Break-glass role** exists in every production account: `emergency-admin-role`.
- **Requires:** MFA + justification (even at 3 AM — documented).
- **Access method:** SSO with elevated permission set (time-limited — 1 hour max).
- **Logging:** CloudTrail captures everything. PagerDuty alert triggers to security team: "Break glass used by X on account Y."
- **Post-incident:** Review next business day — was it justified? What was changed? Do we need a permanent fix?
- **Key principle:** Break glass exists so engineers DON'T go around the system. If access is impossible → they'll find dangerous workarounds.

---

*End of Q&A Bank — 20 questions covering all 7 dimensions*
