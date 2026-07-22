# Project 4: Multi-Account AWS Landing Zone

## Managing 15+ AWS Accounts with Governance & Security

**Author:** Siddharth Patel  
**Role:** Staff/Principal DevOps & Cloud Engineer (12 YOE)  
**Technologies:** AWS Organizations, SCPs, Control Tower, Terraform, IAM Identity Center, OIDC

---

## Table of Contents

1. What is a Landing Zone?
2. Why Multiple Accounts?
3. Account Structure (Organization Design)
4. Service Control Policies (SCPs)
5. IAM Identity Center (SSO)
6. CI/CD Cross-Account Access (OIDC)
7. Centralized Security (GuardDuty, Security Hub, CloudTrail)
8. Account Vending (Self-Service)
9. Terraform Implementation
10. Interview Talking Points

---

## 1. What is a Landing Zone?

A Landing Zone is a **pre-configured, secure, multi-account AWS environment** that's ready for teams to use.

**Simple analogy:** Building an apartment complex.
- You don't let each tenant build their own walls and plumbing
- You (platform team) build the structure: walls, electricity, plumbing, fire exits, security
- Tenants (dev teams) move in and use the furnished apartment
- They can arrange furniture (deploy apps) but can't remove fire exits (security guardrails)

**Without Landing Zone:** Each team creates their own account, does whatever they want. Result = security holes, no audit trail, cost chaos, impossible to manage.

**With Landing Zone:** Every account is born with security baseline, guardrails, logging, networking — automatically.

---

## 2. Why Multiple Accounts?

**Why not one big account for everything?**

| Risk with Single Account | How Multi-Account Fixes It |
|---|---|
| Dev mistake deletes prod database | Dev and prod in separate accounts — no access between them |
| One team's permissions leak to another | Each team in own account — blast radius contained |
| Cost attribution impossible | Each account = separate bill — instant chargeback |
| Service limits shared | Each account has own limits (VPC, EC2, Lambda) |
| Compliance scope too large | Only prod account is audited — reduces scope |
| One compromised credential affects all | Attacker in dev account can't reach prod |

**Rule of thumb:** Separate accounts for things that should never affect each other.

---

## 3. Account Structure (Organization Design)

### What is an OU (Organizational Unit)?

**OU = Organizational Unit** — a logical folder/group within AWS Organizations that contains AWS accounts.

**Simple analogy:** Think of a company building with floors.
- The building = your AWS Organization
- Each floor = an OU (Security floor, Production floor, Dev floor)
- Each office on a floor = an AWS Account
- Building rules per floor = SCPs (Service Control Policies applied at OU level)

**Why OUs matter:** You apply SCPs at the OU level. All accounts inside that OU inherit the same guardrails automatically — no need to configure each account individually. Move an account to a different OU → it instantly gets that OU's policies.

```
Management Account (root — billing only, no workloads ever)
│
├── Security OU
│   ├── Log Archive Account     (centralized CloudTrail, Config, Flow Logs)
│   └── Security Tooling Account (GuardDuty admin, Security Hub, Inspector)
│
├── Infrastructure OU
│   ├── Network Account          (Transit Gateway, VPN, Direct Connect, DNS)
│   └── Shared Services Account  (CI/CD runners, container registry, Vault)
│
├── Workloads OU
│   ├── Production OU
│   │   ├── App-A Prod Account
│   │   ├── App-B Prod Account
│   │   └── Data Platform Prod Account
│   └── Non-Production OU
│       ├── App-A Dev Account
│       ├── App-A Staging Account
│       └── Sandbox Account (experiments, auto-delete after 7 days)
│
└── Sandbox OU
    └── Developer Sandbox Accounts (limited budget, auto-cleanup)
```

**Key principles:**
- Management account: ONLY for billing and Organizations. Never deploy workloads here.
- Separate OU per purpose — SCPs apply per OU (all prod accounts get same guardrails)
- Shared Services: CI/CD, ECR, Vault — used by all accounts
- Log Archive: immutable logs — even admin can't delete (SCP prevents it)

---

## 4. Service Control Policies (SCPs)

### What are SCPs?

Guardrails that limit what anyone (even admin) can do in an account. Applied at OU level — all accounts under that OU inherit the restriction.

**Simple analogy:** Building fire codes. Even if you own the apartment (have admin access), you CANNOT remove the fire exit. SCPs are those fire codes for AWS accounts.

### Example SCPs

**Applied to ALL OUs (root level):**
```json
{
  "Effect": "Deny",
  "Action": [
    "organizations:LeaveOrganization",
    "cloudtrail:StopLogging",
    "cloudtrail:DeleteTrail",
    "config:StopConfigurationRecorder"
  ],
  "Resource": "*"
}
```
*Nobody can disable logging or leave the organization — not even account admin.*

**Applied to Production OU:**
```json
{
  "Effect": "Deny",
  "Action": "*",
  "Resource": "*",
  "Condition": {
    "StringNotEquals": {
      "aws:RequestedRegion": ["us-east-1", "eu-west-1"]
    }
  }
}
```
*Production can only use 2 approved regions — prevents accidental resources elsewhere.*

**Applied to Sandbox OU:**
```json
{
  "Effect": "Deny",
  "Action": [
    "ec2:RunInstances"
  ],
  "Condition": {
    "StringNotEquals": {
      "ec2:InstanceType": ["t3.small", "t3.medium"]
    }
  }
}
```
*Sandbox users can only launch small instances — prevents cost explosion.*

### SCP Strategy

| OU | SCPs Applied |
|---|---|
| Root (all accounts) | Deny leave org, deny disable logging, require IMDSv2 |
| Production | Restrict regions, deny public S3, require encryption, deny delete VPC |
| Non-Production | Restrict regions, limit instance sizes |
| Sandbox | Max budget $100, limited services, auto-cleanup |

---

## 5. IAM Identity Center (SSO)

### What is it?

Single Sign-On for all AWS accounts. Users log in ONCE (via company directory — Okta, Azure AD, Google) and can switch between accounts based on their role.

**Without SSO:** Each developer has IAM user in each account (15 accounts = 15 passwords = nightmare).

**With SSO:** Developer logs into portal → sees all accounts they have access to → clicks to switch. No IAM users anywhere.

### Permission Sets (Role-Based)

| Permission Set | Who Gets It | What They Can Do |
|---|---|---|
| AdministratorAccess | Platform team | Everything (in infra accounts only) |
| DeveloperAccess | Dev teams | Deploy apps, read logs (own accounts only) |
| ReadOnlyAccess | Everyone | View resources (all accounts — for debugging) |
| SecurityAudit | Security team | Read security findings (all accounts) |
| BillingAccess | Finance | View costs (management account only) |

**Flow:** User → Okta/AD login → Identity Center → Assume role in target account → Temporary credentials (1 hour) → Expires automatically

---

## 6. CI/CD Cross-Account Access (OIDC)

### What is OIDC? (Simple English)

**OIDC = OpenID Connect** — a way for your CI/CD pipeline (GitHub Actions) to prove its identity to AWS and get temporary access WITHOUT storing any passwords or access keys.

**Simple analogy — Hotel key card system:**
- **Old way (Access Keys):** You get a **master key** that opens every room forever. If you lose it, anyone can get in. You must change all locks manually.
- **OIDC way:** You go to hotel reception (AWS), show your ID card (GitHub token), and get a **temporary key card** that opens only YOUR room and expires in 15 minutes. Lost it? Useless in 15 minutes anyway.

**Why OIDC over Access Keys?**

| Old Way (Access Keys) | OIDC Way |
|---|---|
| Permanent keys stored in GitHub secrets | No keys stored anywhere |
| Works from any repo/branch if leaked | Only YOUR specific repo + specific branch |
| Must manually rotate every 90 days | Auto-expires in 15 min (zero rotation) |
| If leaked → permanent access until you notice | If leaked → useless in 15 min |
| Hard to audit "who used this key?" | CloudTrail shows exactly which repo/branch/workflow |

**One-liner:** OIDC = GitHub proves who it is → AWS gives 15-min temporary credentials → no passwords stored anywhere.

### The Problem

CI/CD pipeline (GitHub Actions) needs to deploy to multiple accounts. How to give access WITHOUT storing long-lived keys?

### The Solution: OIDC Federation

```
GitHub Actions → "I am repo siddharthpatel1993/app, branch main"
       │
       ▼
AWS IAM OIDC Provider → "I trust GitHub's token issuer"
       │
       ▼
IAM Role (in target account) → "This role can be assumed by this specific repo+branch"
       │
       ▼
Temporary credentials (15 min) → Deploy → Credentials expire
```

**No access keys stored anywhere. No secrets to rotate. Scoped to exact repo + branch.**

### Terraform for OIDC

```hcl
# In each target account
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github_deploy" {
  name = "github-deploy-role"
  assume_role_policy = jsonencode({
    Statement = [{
      Effect = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:sub" = "repo:siddharthpatel1993/app:ref:refs/heads/main"
        }
      }
    }]
  })
}
```

**Result:** Only `main` branch of your specific repo can deploy. Feature branches cannot. Other repos cannot. No keys to leak.

---

## 7. Centralized Security

### Architecture

```
All 15 Accounts → Send findings → Security Tooling Account
                                         │
                                    ┌────▼────┐
                                    │Security │
                                    │  Hub    │ (single pane of glass)
                                    └────┬────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
       ┌──────▼──────┐          ┌───────▼───────┐          ┌──────▼──────┐
       │  GuardDuty  │          │  AWS Config   │          │  CloudTrail │
       │  (threats)  │          │  (compliance) │          │  (audit)    │
       └─────────────┘          └───────────────┘          └─────────────┘
```

| Service | What It Does | Example Finding |
|---|---|---|
| GuardDuty | ML-based threat detection | "EC2 instance communicating with known C2 server" |
| Security Hub | Aggregates all findings, compliance scoring | "15 accounts: 92% CIS compliance" |
| AWS Config | Checks resource configurations continuously | "S3 bucket xyz is publicly accessible" |
| CloudTrail | Logs every API call across all accounts | "Who deleted that RDS instance at 3 AM?" |
| Inspector | Scans EC2/containers for CVEs | "AMI has critical Log4Shell vulnerability" |

### Centralized Logging (Log Archive)

```
Every account → CloudTrail → Organization Trail → S3 in Log Archive Account
                                                    │
                                              SCP: Nobody can delete
                                              Lifecycle: Glacier after 90 days
                                              Retention: 7 years (compliance)
```

---

## 8. Account Vending (Self-Service)

### What is it?

New team needs an AWS account? They don't file a ticket and wait 2 weeks. They request via self-service — account is created with full baseline in <30 minutes.

### What Gets Auto-Applied to Every New Account

1. VPC with standard CIDR (from central IPAM)
2. Transit Gateway attachment (connectivity to shared services)
3. IAM roles (deploy role, read-only role, break-glass role)
4. CloudTrail → Log Archive
5. GuardDuty enrolled
6. Config rules enabled
7. Security Hub registered
8. Default SCPs from OU
9. SSO permission sets assigned
10. Budget alarm ($500 default)

### Flow

```
Team Lead → Requests via ServiceNow/Jira
    → Approved by Platform Team
    → Control Tower Account Factory / Terraform triggered
    → New account created in correct OU
    → Baseline applied automatically (Terraform + StackSets)
    → SSO access provisioned
    → Team notified: "Your account is ready"
    
Time: < 30 minutes (automated)
```

---

## 9. Terraform Implementation

### Structure

```
terraform/
├── organization/
│   ├── accounts.tf         (aws_organizations_account for each)
│   ├── ous.tf              (organizational units)
│   ├── scps.tf             (service control policies)
│   └── delegated_admin.tf  (GuardDuty, SecurityHub delegation)
├── baseline/               (applied to every account)
│   ├── cloudtrail.tf
│   ├── config.tf
│   ├── guardduty.tf
│   ├── iam_roles.tf
│   ├── vpc.tf
│   └── budget.tf
├── networking/             (shared — Transit Gateway, DNS)
│   ├── transit_gateway.tf
│   ├── route53.tf
│   └── vpc_peering.tf
└── identity/
    ├── identity_center.tf
    ├── permission_sets.tf
    └── github_oidc.tf
```

---

---

## How This Project Connects to Other Projects (Portfolio Context)

### The Landing Zone is the FOUNDATION

This project isn't standalone — it's the platform that makes all other projects possible in an enterprise:

```
Project 4: Landing Zone (THE FOUNDATION)
│
├── Creates the AWS accounts where everything lives
├── Networking (VPC, Transit Gateway) that Project 2 uses
├── OIDC that Project 1's Jenkins/GitHub Actions uses to deploy
├── Security guardrails (SCPs) that protect Project 2 & 3
│
├──► Project 2 (3-Tier AWS) lives INSIDE the "Workloads/Prod" account
├──► Project 3 (EKS) lives INSIDE the "Workloads/Prod" account
└──► Project 1 (CI/CD Pipeline) lives INSIDE the "Shared Services" account
     and uses OIDC to deploy INTO the Workloads accounts
```

### End-to-End Flow: How All Projects Work Together

```
Developer pushes code
    │
    ▼
Project 1: Jenkins (in Shared Services Account)
    │ uses OIDC (Project 4) to assume role in Prod Account
    ▼
Project 3: Deploys to EKS cluster (in Workloads/Prod Account)
    │ which runs inside
    ▼
Project 2: VPC/Networking (created by Landing Zone - Project 4)
    │
    ▼
All protected by SCPs (Project 4) — can't disable logging, can't open DB to internet
```

### Where Each Component Lives

| Component | AWS Account (from Landing Zone) | Why Here |
|---|---|---|
| Jenkins / CI/CD platform | Shared Services Account (Infrastructure OU) | Shared by all teams, not owned by one app |
| Docker Registry (ECR) | Shared Services Account | All teams push/pull images |
| EKS Cluster (Production) | App Prod Account (Workloads/Production OU) | Isolated from dev, SCPs protect it |
| 3-Tier App (ALB, ASG, RDS) | App Prod Account (Workloads/Production OU) | Same account as EKS or separate per-app |
| EKS Cluster (Dev/Staging) | App Dev Account (Workloads/Non-Production OU) | Developers can experiment freely here |
| CloudTrail / Audit Logs | Log Archive Account (Security OU) | Immutable — nobody can delete evidence |
| GuardDuty / Security Hub | Security Tooling Account (Security OU) | Central security visibility |
| Terraform State (S3 + DynamoDB) | Shared Services Account | Central, access-controlled |

### Who is Responsible for This at 12 YOE?

**You are.** This is a core responsibility of a Senior/Staff DevOps & Cloud Engineer.

| Activity | Your Responsibility |
|---|---|
| Design OU structure | ✅ You design it based on business/compliance needs |
| Write SCPs | ✅ You write, test, and apply them |
| Implement SSO | ✅ You configure IAM Identity Center |
| Set up OIDC for CI/CD | ✅ You build this (no access keys anywhere) |
| Account vending automation | ✅ You build the Terraform that creates accounts with baseline |
| Centralized security (GuardDuty, Config) | ✅ You configure and maintain |
| Present to leadership/auditors | ✅ You explain and defend the design |
| Evolve as company grows | ✅ New teams, new compliance, new regions — you adapt |

**What's NOT your responsibility:** Budget approval (VP/Director), compliance requirements definition (Security team), which teams exist (Engineering managers).

### Interview Key Point

> "The Landing Zone is the foundation. My CI/CD pipeline, 3-tier infrastructure, and Kubernetes clusters all run within the governed accounts it creates. Without it, you'd have 15 accounts with no guardrails, no audit trail, no cost attribution, and no security baseline. The Landing Zone makes enterprise-grade operations possible."

---

## 10. Interview Talking Points

### 2-Minute Version

"Architected a 15-account AWS Organization with proper OU structure — Security, Infrastructure, Production, Non-Production, and Sandbox. SCPs enforce guardrails that even admin can't bypass: no disabling logging, region restrictions, encryption required. IAM Identity Center provides SSO via corporate directory — no IAM users in any account. CI/CD uses OIDC federation with GitHub Actions — no long-lived keys, scoped to specific repo and branch. Centralized security: GuardDuty for threats, Config for compliance, CloudTrail immutable in log archive. Account vending delivers a fully baselined account in under 30 minutes."

### Key Interview Q&A

**Q: "How do you prevent a developer from opening SSH to the world in production?"**  
A: Three layers. SCP denies creating security groups with 0.0.0.0/0 on port 22. AWS Config rule detects it and auto-remediates (Lambda removes the rule). Terraform IaC scanning catches it at PR time before it even applies.

**Q: "How does CI/CD deploy to production account without storing keys?"**  
A: OIDC federation. GitHub Actions presents a token saying "I am repo X, branch main." AWS IAM trusts GitHub's token issuer and issues 15-minute temporary credentials. No secrets stored anywhere. Only main branch can deploy to prod — enforced in the trust policy condition.

**Q: "What if someone needs emergency access to production?"**  
A: Break-glass role in each prod account. Requires MFA + justification ticket. Access logged, auto-expires in 1 hour, triggers PagerDuty alert to security team. Reviewed post-incident.
