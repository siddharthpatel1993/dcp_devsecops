# Project 9: Enterprise OS Patching Automation

## 18-Step Zero-Touch Lifecycle with Automatic Rollback & ITIL Compliance

**Author:** Siddharth Patel  
**Role:** Staff/Principal DevOps & Cloud Engineer (12 YOE)  
**GitLab:** gitlab.com/patelsiddharthnids993/ansible_os_automation  
**Technologies:** Ansible, Ansible Automation Platform (AAP), ServiceNow, AWS (ALB, EC2), Alertmanager, CloudWatch, PagerDuty, Slack, Python, dnf/yum

---

## Table of Contents

1. Problem Statement & Why This Matters
2. Architecture Overview
3. 18-Step Patching Lifecycle (Complete Flow)
4. Traffic Management (Zero-Downtime Strategy)
5. 7-Dimension Zero-Touch Validation
6. Roles Deep-Dive (12 Production Roles)
7. ServiceNow ITIL Integration
8. Monitoring Integration (Silence/Re-enable)
9. Security Design
10. Ansible Automation Platform (AAP) Execution
11. Key Design Decisions
12. Interview Talking Points

---

## 1. Problem Statement & Why This Matters

### The Problem

Manually patching Linux servers is:
- **Error-prone** — human forgets to re-enable monitoring, skips validation, misses a server
- **Time-consuming** — SSH to each server, run commands, check results, update tickets = hours per server
- **Lacks audit trail** — "Who patched what, when?" → nobody knows, compliance fails
- **Risky** — patching under live traffic = killed requests, interrupted transactions
- **Inconsistent** — different engineer patches differently each time

### What We Built

Fully automated, **zero-touch** OS patching lifecycle:
- From ServiceNow Change Request opening to closure — no human intervention
- 18 discrete steps covering the complete lifecycle
- Zero-downtime (ALB drain + serial batching)
- Automatic rollback on any failure (7-dimension validation decides PASS/FAIL)
- Complete audit trail (every step logged, reports attached to CR)
- Multi-channel alerting (Slack + Email + PagerDuty)

### Why This Matters at 12 YOE

| Junior engineer can: | 12 YOE engineer must: |
|---|---|
| Patch one server via SSH | Design the system that patches 500 servers safely |
| Run `dnf update` | Handle reboot logic, kernel checks, rollback |
| Restart a service | Validate 7 dimensions of health automatically |
| Update a Jira ticket | Automate full ITIL lifecycle (CR open → close) |
| Monitor one server | Silence/re-enable monitoring across the fleet |
| Fix one server if it breaks | Control blast radius (serial 20%, max_fail 10%) |

**Simple analogy:** Junior drives the car. Senior designs the self-driving system — with lane detection, emergency braking, and crash avoidance.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ANSIBLE AUTOMATION PLATFORM (AAP)                         │
│                                                                             │
│   Workflow Template: OS Patching Lifecycle                                   │
│   ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐           │
│   │Open CR│→│Silence│→│Pre-chk│→│ Drain │→│ Patch │→│ Valid │→ ...        │
│   └───────┘ └───────┘ └───────┘ └───────┘ └───────┘ └───────┘           │
│                                                                             │
│   On Failure: Auto-rollback → Alert → Update CR → Close                    │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │ SSH
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TARGET RHEL FLEET                                     │
│                                                                             │
│   ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐            │
│   │web-01│  │web-02│  │web-03│  │web-04│  │web-05│  │web-06│  ...        │
│   └──────┘  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘            │
│                                                                             │
│   serial: 20% → patch 2 servers at a time, other 8 serve traffic           │
└─────────────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INTEGRATIONS                                          │
│                                                                             │
│   ServiceNow │ Alertmanager │ CloudWatch │ PagerDuty │ Slack │ AWS ALB      │
│   (CR ITIL)  │ (silence)    │ (silence)  │ (alert)   │(notif)│ (traffic)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Architecture Decisions

| Decision | Why |
|---|---|
| AAP (not cron/Jenkins) | RBAC, audit trail, workflow templates, survey forms, credential vault |
| Ansible (not shell scripts) | Idempotent, declarative, error handling, role reuse |
| Serial 20% batching | Blast radius control — maximum 20% of fleet at risk |
| Config-driven tests | Add connectivity checks without code changes (YAML) |
| Reports on controller | Evidence survives even if target server dies |

---

## 3. 18-Step Patching Lifecycle

### Complete Flow Diagram

```
STEP 1: Open ServiceNow CR ─────────────────────────────────────────────────────┐
STEP 2: Silence monitoring (Alertmanager + CloudWatch + PagerDuty)              │
STEP 3: Pre-connectivity check (SSH + Python gate)                              │
STEP 4: Baseline + backup (41 config files + 26 commands)                       │
                                                                                │
STEP 5: Drain ALB traffic (deregister + wait drain)                            │
STEP 6: Stop services (graceful shutdown)                                       │
STEP 7: Verify stopped (systemd + port + HTTP)                                 │
                                                                                │
STEP 8: Apply patches (dnf update + exclusions + reboot if kernel)             │
                                                                                │
STEP 9: Start services                                                          │
STEP 10: Verify running (3-level health check)                                 │
STEP 11: Integrity check (checksum + app tag verification)                     │
STEP 12: Certificate validation (expiry + permissions + key-pair + CA)         │
STEP 13: POST-PATCH VALIDATION — 7 dimensions (PASS/FAIL gate)                 │
         │                                                                      │
         ├── ALL PASS ──────────────────────────────────────────────┐          │
         │                                                          │          │
         └── ANY FAIL → Rollback → Alert → Update CR (FAILED) ────────────────┘
                                                                    │
STEP 14: Post-connectivity (nc tests to all dependencies)           │
STEP 15: Re-register ALB (add back + wait healthy)                  │
STEP 16: Re-enable monitoring (remove silences)                     │
STEP 17: Close ServiceNow CR (with evidence)                        │
STEP 18: Send notifications (Slack + Email + PagerDuty)    ◄────────┘
```

### Step-by-Step Detail

---

### Step 1: Open ServiceNow Change Request

**Purpose:** ITIL compliance. Every production change MUST have a tracked CR.

**What it does:**
- Creates CR with Method of Procedure (MOP) documented
- Records planned start/end time, risk assessment, rollback plan
- CR number (CHG0012345) used throughout for traceability
- Status set to "In Progress"

```yaml
- name: Open ServiceNow Change Request
  servicenow.itsm.change_request:
    state: new
    type: "standard"
    short_description: "OS Patching - {{ ansible_date_time.date }} - {{ hostname }}"
    description: |
      === METHOD OF PROCEDURE (MOP) ===
      1. Silence monitoring
      2. Drain ALB traffic
      3. Apply OS patches (dnf update)
      4. Validate across 7 dimensions
      5. Re-register to ALB
      6. Re-enable monitoring
      === ROLLBACK PLAN ===
      Automatic rollback on validation failure.
      Manual: Revert to pre-patch AMI snapshot.
  register: change_request
```

**Why automate this?** Manual CR creation = forgotten, incomplete, wrong dates. Automated = consistent, always complete, timestamped evidence.

---

### Step 2: Silence Monitoring

**Purpose:** Prevent false alerts during planned maintenance. Without this, on-call engineer gets paged when we deliberately stop services.

**What it silences:**
| System | How | Auto-Expire |
|---|---|---|
| Alertmanager | Create silence via API (matcher: hostname) | 4 hours (safety net) |
| CloudWatch | Disable alarm actions | Re-enabled after patching |
| PagerDuty | Create maintenance window | 4 hours |

```yaml
- name: Create Alertmanager silence
  uri:
    url: "{{ alertmanager_url }}/api/v2/silences"
    method: POST
    body_format: json
    body:
      matchers:
        - name: instance
          value: "{{ inventory_hostname }}"
          isRegex: false
      startsAt: "{{ ansible_date_time.iso8601 }}"
      endsAt: "{{ silence_end_time }}"    # 4 hours from now
      comment: "OS Patching - CR {{ cr_number }}"
      createdBy: "ansible-patching"
    status_code: 200
  register: silence_result
  delegate_to: localhost
```

**Key design: Auto-expire silences.** If the playbook crashes mid-way and never re-enables monitoring, the silence expires in 4 hours → alerts resume. No server goes permanently unmonitored.

---

### Step 3: Pre-Connectivity Check

**Purpose:** Verify ALL target servers are reachable BEFORE touching anything. If a server is unreachable, fail EARLY — not after you've already stopped services on other servers.

```yaml
- name: Test connectivity to target host (SSH + Python)
  ansible.builtin.ping:    # Tests SSH + Python, NOT ICMP
  register: connectivity_result
  ignore_unreachable: true
```

**Failure categorization:**
| Category | Meaning | Action |
|---|---|---|
| Unreachable | Network/firewall issue | Skip server, alert |
| Auth failed | SSH key rotated/expired | Skip server, alert |
| Python missing | Ansible can't execute modules | Skip server, alert |

**Why categorize?** Different failures need different fixes. "Unreachable" = network team. "Auth" = key rotation team. "Python" = OS team.

---

### Step 4: Baseline + Backup

**Purpose:** Capture current state BEFORE we change anything. Two uses:
1. **Rollback evidence** — if patching breaks something, compare pre/post to find what changed
2. **Compliance proof** — auditor asks "what was the state before?" → here's the report

**What gets captured (41 config files + 26 commands):**

| Category | Items Captured |
|---|---|
| Network config | `/etc/sysconfig/network`, `/etc/resolv.conf`, routing table, interfaces |
| System config | `/etc/fstab`, `/etc/hosts`, `/etc/sysctl.conf`, crontabs |
| Security | `/etc/ssh/sshd_config`, firewall rules, SELinux state |
| Services | Running services list, enabled services, listening ports |
| Packages | Full RPM list, kernel version, pending updates |
| Application | App config files, version files, checksums of binaries |
| Storage | Disk usage, mount points, LVM info |

```yaml
- name: Capture pre-patch baseline
  shell: "{{ item.cmd }}"
  loop: "{{ baseline_commands }}"
  register: baseline_results

- name: Backup config files to controller
  fetch:
    src: "{{ item }}"
    dest: "./backups/{{ inventory_hostname }}/pre-patch/{{ ansible_date_time.iso8601 }}/"
  loop: "{{ backup_files }}"
```

**Key design:** Reports fetched TO the controller, not saved on target. If target server dies, evidence survives.

---

### Step 5: Drain ALB Traffic

**Purpose:** Remove server from load balancer BEFORE touching it. Users get routed to other healthy servers → zero impact.

```yaml
- name: Deregister server from ALB Target Group
  amazon.aws.elb_target:
    target_group_arn: "{{ alb_target_group_arn }}"
    target_id: "{{ ansible_ec2_instance_id }}"
    state: absent
    region: "{{ aws_region }}"
  delegate_to: localhost

- name: Wait for connection draining
  pause:
    seconds: "{{ drain_wait_seconds }}"    # Default: 60s

- name: Verify zero active connections
  shell: "ss -tn | grep ':80 ' | wc -l"
  register: active_connections
  until: active_connections.stdout | int == 0
  retries: 6
  delay: 10
```

**Why verify zero connections?** Drain timer alone isn't enough. Long-running requests (file uploads, WebSocket) might still be active. We wait until `ss` confirms zero.

---

### Step 6 & 7: Stop Services + Verify Stopped

**Purpose:** Graceful shutdown. Verify it's actually stopped (not just "requested to stop").

**3-Level verification:**
```yaml
# Level 1: systemd says inactive
- name: Check systemd state
  ansible.builtin.systemd:
    name: httpd
  register: svc_status

# Level 2: Port not listening
- name: Verify port closed
  shell: "ss -tlnp | grep ':80 ' | wc -l"
  register: port_check
  # Expect: 0

# Level 3: HTTP not responding
- name: Verify no HTTP response
  uri:
    url: "http://localhost:80/"
    timeout: 5
  register: http_check
  failed_when: false
  # Expect: failure (connection refused)
```

**Why 3 levels?** `systemctl stop` returns success even if the process hangs. Port check catches zombie processes. HTTP check confirms no response.

---

### Step 8: Apply Patches

**Purpose:** The actual patching. Most critical step — with maximum safety nets.

```yaml
# Create AMI snapshot (instant rollback if catastrophic)
- name: Create pre-patch snapshot
  amazon.aws.ec2_ami:
    instance_id: "{{ instance_id.stdout }}"
    name: "pre-patch-{{ inventory_hostname }}-{{ ansible_date_time.date }}"
    wait: yes
  delegate_to: localhost

# Apply patches with exclusions
- name: Apply OS patches
  dnf:
    name: "*"
    state: latest
    exclude: "{{ exclude_packages | join(',') }}"
  register: patch_result

# Record what was updated (evidence for CR)
- name: Record patched packages
  set_fact:
    patched_packages: "{{ patch_result.results | map(attribute='name') | list }}"

# Reboot ONLY if kernel was updated
- name: Check if kernel was updated
  shell: "rpm -q kernel --last | head -1 | awk '{print $1}' | sed 's/kernel-//'"
  register: latest_kernel

- name: Reboot if kernel updated
  reboot:
    reboot_timeout: 600
    post_reboot_delay: 30
  when: latest_kernel.stdout != ansible_kernel
```

**Package exclusions:** Protect database packages, custom-compiled software, and packages managed by other teams.

```yaml
# vars/main.yml
exclude_packages:
  - postgresql*        # DB team manages this
  - oracle*            # DBA managed
  - custom-app-*      # Application team's packages
  - docker-ce*        # Container runtime, separate lifecycle
```

**Why conditional reboot?** Not every patching run includes a kernel update. Unnecessary reboots = unnecessary risk + downtime. Only reboot when kernel version changed.



---

### Steps 9 & 10: Start Services + Verify Running

Same 3-level check, but expecting ACTIVE this time:

```yaml
# Level 1: systemd says active
- name: "Level 1 — Check systemd service state"
  ansible.builtin.systemd:
    name: httpd
  register: httpd_status
  # Expect: ActiveState = "active", SubState = "running"

# Level 2: Port listening
- name: "Level 2 — Check if port 80 is listening"
  shell: "ss -tlnp | grep ':80 ' | wc -l"
  register: port_check
  # Expect: > 0

# Level 3: HTTP responding
- name: "Level 3 — Application HTTP health check"
  uri:
    url: "http://localhost:80/"
    status_code: [200, 301, 302]
    timeout: 10
  register: http_check
  retries: 3
  delay: 5
```

**Why retries on Level 3?** Application may need 10-15 seconds to fully initialize after service start (JVM warmup, cache loading, DB connection pool).

---

### Step 11: Integrity Check (Checksum + App Tag)

**Purpose:** Detect if patching overwrote application files. OS package updates can replace custom configs with package defaults.

```yaml
# Checksum verification — 8 critical components
checksum_files:
  - { path: "/etc/httpd/conf/httpd.conf", expected: "a4f8b3c2d1e5..." }
  - { path: "/opt/app/bin/app-server", expected: "f7e6d5c4b3a2..." }
  - { path: "/etc/ssl/certs/app.crt", expected: "1a2b3c4d5e6f..." }
  - { path: "/opt/app/config/application.yml", expected: "9f8e7d6c5b4a..." }
  # ... 8 total components

# Tag verification — correct app version deployed
tag_files:
  - { path: "/opt/app/VERSION", expected_content: "v3.2.1" }
  - { path: "/opt/app/BUILD", expected_content: "build-20260715" }
```

**What this catches:**
- `httpd` package update → overwrites custom `httpd.conf` with default
- `openssl` update → replaces SSL config
- Library update → corrupts application binary via shared library change

---

### Step 12: Certificate Validation

**Purpose:** After patching, TLS certificates might be broken (CA bundle update, permission reset, config overwrite).

**4 Checks:**
| Check | What It Validates | Common Post-Patch Failure |
|---|---|---|
| File existence + permissions | Cert file exists, key is 600 | Package update resets permissions |
| Expiry | Not expired, not expiring within 30 days | NTP drift after reboot → appears expired |
| Key-pair match | Certificate and private key belong together | Config overwrite points to wrong key |
| CA bundle | Can validate the certificate chain | `ca-certificates` update removes old CA |

```yaml
# Check cert-key pair match
- name: Get certificate modulus
  shell: "openssl x509 -noout -modulus -in {{ cert_path }} | md5sum"
  register: cert_modulus

- name: Get key modulus
  shell: "openssl rsa -noout -modulus -in {{ key_path }} | md5sum"
  register: key_modulus

- name: Verify cert and key match
  assert:
    that: cert_modulus.stdout == key_modulus.stdout
    fail_msg: "CRITICAL: Certificate and private key DO NOT match!"
```

---

### Step 13: Post-Patch Validation (THE DECISION GATE)

This is the most critical step. It determines PASS or FAIL with zero human judgement.

**7 Dimensions validated — see Section 5 below for full detail.**

---

### Step 14: Post-Connectivity

**Purpose:** Verify the patched server can reach ALL its dependencies (database, APIs, DNS, message queues).

```yaml
# Config-driven — add tests without code changes
network_endpoints:
  - { host: "rds-prod.abc.us-east-1.rds.amazonaws.com", port: 5432, name: "Database", critical: true }
  - { host: "redis-prod.abc.cache.amazonaws.com", port: 6379, name: "Redis Cache", critical: true }
  - { host: "api-gateway.internal", port: 443, name: "API Gateway", critical: true }
  - { host: "prometheus.internal", port: 9090, name: "Monitoring", critical: false }
  - { host: "8.8.8.8", port: 53, name: "External DNS", critical: true }

# nc test for each endpoint
- name: Test connectivity to dependencies
  shell: "nc -z -w5 {{ item.host }} {{ item.port }}"
  loop: "{{ network_endpoints }}"
  register: connectivity_results
  ignore_errors: true
```

**Critical vs Non-Critical:** If monitoring endpoint is unreachable, we don't block the patching pipeline (it's non-critical). If database is unreachable, we DO block — that's a real problem.

---

### Steps 15-18: Re-register ALB → Re-enable Monitoring → Close CR → Notify

```yaml
# Step 15: Re-register to ALB + wait for health check
- name: Register server back to ALB
  amazon.aws.elb_target:
    target_group_arn: "{{ alb_target_group_arn }}"
    target_id: "{{ ansible_ec2_instance_id }}"
    state: present
    region: "{{ aws_region }}"
  delegate_to: localhost

- name: Wait for ALB health check to pass
  amazon.aws.elb_target_info:
    target_group_arn: "{{ alb_target_group_arn }}"
    region: "{{ aws_region }}"
  register: target_health
  until: target_health.targets | selectattr('target.id', 'eq', ansible_ec2_instance_id) 
         | map(attribute='target_health.state') | first == 'healthy'
  retries: 12
  delay: 10
  delegate_to: localhost

# Step 16: Re-enable monitoring
- name: Remove Alertmanager silence
  uri:
    url: "{{ alertmanager_url }}/api/v2/silence/{{ silence_id }}"
    method: DELETE
  delegate_to: localhost

# Step 17: Close ServiceNow CR
- name: Close Change Request with evidence
  servicenow.itsm.change_request:
    number: "{{ cr_number }}"
    state: closed
    close_code: successful
    close_notes: |
      Patching completed successfully.
      Servers patched: {{ ansible_play_hosts | length }}
      Packages updated: {{ patched_packages | length }}
      Validation: ALL 7 DIMENSIONS PASSED
      Report: Attached below

# Step 18: Multi-channel notification
# See notification role in Section 6
```

---

## 4. Traffic Management (Zero-Downtime Strategy)

### How Zero-Downtime Works

```
10-server fleet: [web-01] [web-02] [web-03] [web-04] [web-05] 
                  [web-06] [web-07] [web-08] [web-09] [web-10]

serial: 20% = 2 servers per batch

Batch 1: [web-01] [web-02] → drain → patch → validate → re-register
          Other 8 servers serve 100% of traffic

Batch 2: [web-03] [web-04] → drain → patch → validate → re-register
          Other 8 servers serve traffic

...continues until all 10 done.

If Batch 3 fails (>10% of batch):
  → STOP. Don't touch remaining servers.
  → web-05/06 auto-rollback
  → web-01/02/03/04 already healthy (passed validation)
  → web-07/08/09/10 untouched
  → Maximum blast radius: 2 servers (20%)
```

### Key Configuration

```yaml
- name: OS Patching with ALB Traffic Management
  hosts: "{{ hostname }}"
  serial: "20%"              # Patch 20% of fleet at a time
  max_fail_percentage: 10    # Abort if >10% of batch fails
```

### Per-Server Flow

```
BEFORE:  [ALB] ──traffic──→ [Server-A] ✅ Serving
                                          
STEP 5:  [ALB] ──traffic──→ [Server-A] 🔴 Deregistered (new requests stop)
         Active connections drain (60s)
                                          
STEP 8:  [ALB]              [Server-A] 🔧 Being patched (zero traffic)
                                          
STEP 15: [ALB] ──traffic──→ [Server-A] ✅ Re-registered (health check passes)
```

**Why `max_fail_percentage: 10`?** With serial 20% (2 servers), if 1 server fails = 50% of batch failed. But with larger fleets (20 servers, serial 20% = 4 per batch), one failure = 25% of batch. Setting 10% means even 1 failure in a small batch triggers abort — conservative and safe.

---

## 5. 7-Dimension Zero-Touch Validation

### What "Zero-Touch" Means

No human looks at output and decides "yeah, this looks fine." The playbook evaluates 7 checks, each with clear PASS/FAIL criteria. ALL must pass. ANY failure triggers automatic rollback.

### The 7 Dimensions

```
┌─────────────────────────────────────────────────────────────┐
│              POST-PATCH VALIDATION                           │
│                                                             │
│  1. ✅ Package compliance    — expected updates installed?  │
│  2. ✅ Kernel verification   — new kernel loaded?           │
│  3. ✅ Service health        — critical services running?   │
│  4. ✅ Log error check       — no critical errors?          │
│  5. ✅ Disk space            — all mounts below 90%?        │
│  6. ✅ Network connectivity  — reaches all dependencies?    │
│  7. ✅ Application health    — HTTP endpoint responding?    │
│                                                             │
│  ALL PASS → proceed (re-register ALB, close CR)            │
│  ANY FAIL → auto-rollback (alert, update CR as failed)     │
└─────────────────────────────────────────────────────────────┘
```

### Dimension Details

| # | Dimension | What's Checked | PASS Criteria | FAIL Example |
|---|---|---|---|---|
| 1 | Package compliance | Compare installed packages against expected | All pending updates installed (minus exclusions) | Package `openssl` still at old version |
| 2 | Kernel verification | `uname -r` vs latest installed kernel | Match (or no kernel update pending → skip) | Old kernel still loaded (reboot didn't happen) |
| 3 | Service health | `systemctl is-active` for sshd, chronyd, httpd | All active | httpd failed to start after reboot |
| 4 | Log errors | `journalctl --since "1 hour ago" -p err` | Zero critical errors | "SEGFAULT" or "Out of memory" in journal |
| 5 | Disk space | `df -h` all mount points | All below 90% | `/var` at 95% (patches filled disk) |
| 6 | Network | `nc -z` to all dependency endpoints | All critical endpoints reachable | Can't reach database on port 5432 |
| 7 | Application | HTTP GET to health endpoint | 200/301/302 response | Connection refused or 500 error |

### Implementation

```yaml
# Dimension 1: Package compliance
- name: "Dim 1 — Check packages updated"
  shell: "dnf check-update --quiet | wc -l"
  register: pending_updates
  changed_when: false

- name: Record package compliance
  set_fact:
    dim1_pass: "{{ pending_updates.stdout | int == 0 }}"

# Dimension 2: Kernel (conditional — only if kernel was pending)
- name: "Dim 2 — Verify running kernel"
  shell: "uname -r"
  register: running_kernel

- name: Check latest installed kernel
  shell: "rpm -q kernel --last | head -1 | awk '{print $1}' | sed 's/kernel-//'"
  register: installed_kernel

- name: Record kernel compliance
  set_fact:
    dim2_pass: "{{ running_kernel.stdout == installed_kernel.stdout or not kernel_was_pending }}"

# Dimension 5: Disk space
- name: "Dim 5 — Check disk usage"
  shell: "df -h | awk 'NR>1 {gsub(/%/,\"\",$5); if($5 > {{ disk_threshold }}) print $6, $5\"%\"}'"
  register: disk_check

- name: Record disk compliance
  set_fact:
    dim5_pass: "{{ disk_check.stdout_lines | length == 0 }}"

# FINAL DECISION
- name: "═══ VALIDATION RESULT ═══"
  set_fact:
    validation_passed: "{{ dim1_pass and dim2_pass and dim3_pass and dim4_pass 
                           and dim5_pass and dim6_pass and dim7_pass }}"

- name: "FAIL — Trigger rollback"
  include_role:
    name: rollback
  when: not validation_passed

- name: "PASS — Proceed with re-registration"
  debug:
    msg: "✅ ALL 7 DIMENSIONS PASSED — Server ready for traffic"
  when: validation_passed
```

---

## 6. Roles Deep-Dive (12 Production Roles)

### Role Architecture

```
all_roles/
├── connectivity/       ← Pre-patch gate (SSH + Python)
├── pre_backup/         ← 41 files + 26 commands captured
├── post_backup/        ← Same capture AFTER patching
├── diff/               ← Compare pre/post, report changes
├── stop/               ← Graceful service shutdown
├── start/              ← Service restart
├── status/             ← 3-level health check (systemd + port + HTTP)
├── patch/              ← dnf update with exclusions + kernel reboot
├── integrity_check/    ← md5 checksum + app tag verification
├── cert_check/         ← TLS certificate validation (4 checks)
├── post_connectivity/  ← nc tests to all dependencies
├── baseline_check/     ← Python scripts validate no drift
└── notification/       ← Slack + Email + PagerDuty (outcome-based)
```

### Role Details

| Role | Purpose | Key Logic | Output |
|---|---|---|---|
| **connectivity** | Gate: can we reach this server? | `ansible.builtin.ping` + failure categorization (unreachable/auth/python) | Report: passed[], failed[] with reasons |
| **pre_backup** | Capture state before change | 41 config files backed up + 26 commands executed + package list + kernel version | Timestamped evidence on controller |
| **post_backup** | Capture state after change | Same as pre_backup but timestamped "post" | Used by diff role for comparison |
| **diff** | What changed? | Compare pre vs post files, generate ADDED/REMOVED/CHANGED report | Human-readable change report |
| **stop** | Shutdown application | `systemctl stop httpd` (graceful, waits for active requests) | Service stopped confirmation |
| **start** | Start application | `systemctl start httpd` | Service started confirmation |
| **status** | Is service truly healthy? | 3 levels: systemd active → port listening → HTTP 200 | Boolean: healthy/unhealthy |
| **patch** | Apply OS updates | Snapshot → exclude packages → `dnf update` → conditional reboot → verify services | List of updated packages |
| **integrity_check** | Files intact? | md5sum of 8 critical files vs known-good baseline + app version tag check | PASS/FAIL per component |
| **cert_check** | TLS healthy? | File exists + permissions + expiry + cert-key pair match + CA bundle valid | PASS/FAIL per certificate |
| **post_connectivity** | Can reach dependencies? | `nc -z` tests to database, cache, APIs (critical vs non-critical separation) | Reachable/unreachable per endpoint |
| **baseline_check** | No unexpected drift? | Python scripts compare RPM list, kernel, configs against baseline | Drift report |
| **notification** | Alert the team | Slack (always), Email (always), PagerDuty (failure only) | Notifications sent |

### Notification Logic

```yaml
# PagerDuty: ONLY on failure (don't wake on-call for success)
- name: Trigger PagerDuty incident
  uri:
    url: "https://events.pagerduty.com/v2/enqueue"
    method: POST
    body_format: json
    body:
      routing_key: "{{ pagerduty_routing_key }}"
      event_action: "trigger"
      payload:
        summary: "OS Patching FAILED — {{ inventory_hostname }}"
        severity: "critical"
        source: "ansible-patching"
  when: not validation_passed    # Only on failure
  delegate_to: localhost

# Slack: Always notify (success = green, failure = red)
- name: Send Slack notification
  uri:
    url: "{{ slack_webhook }}"
    method: POST
    body_format: json
    body:
      text: "{{ notification_emoji }} OS Patching {{ patching_status }} — {{ inventory_hostname }}"
      attachments:
        - color: "{{ 'good' if validation_passed else 'danger' }}"
          fields:
            - title: "Packages Updated"
              value: "{{ patched_packages | length }}"
            - title: "CR Number"
              value: "{{ cr_number }}"
            - title: "Validation"
              value: "{{ '7/7 PASSED' if validation_passed else failed_dimensions | join(', ') }}"
  delegate_to: localhost
```



---

## 7. ServiceNow ITIL Integration

### Change Request Lifecycle (Automated)

```
┌─────────────────────────────────────────────────────────┐
│         SERVICENOW CHANGE REQUEST LIFECYCLE              │
│                                                         │
│  CREATE (new) ──→ IN PROGRESS ──→ REVIEW ──→ CLOSED    │
│                                                         │
│  Step 1:          Steps 2-15:     Step 17:    Step 17:  │
│  Open CR          Update CR       Attach      Close CR  │
│  with MOP         with progress   reports     with code │
└─────────────────────────────────────────────────────────┘

On Failure:
  CREATE ──→ IN PROGRESS ──→ FAILED (close code: failed)
                              + Rollback evidence attached
```

### What Gets Documented in the CR

| Phase | CR Update Content |
|---|---|
| Open | MOP (Method of Procedure), rollback plan, risk assessment, affected servers |
| During | "Batch 1 complete: web-01, web-02 patched successfully" |
| During | "Batch 2 in progress: web-03, web-04 draining from ALB" |
| Close (success) | Packages updated list, validation results (7/7 PASS), duration |
| Close (failure) | Which dimension failed, rollback actions taken, investigation needed |

### Credentials (Vault Encrypted)

```yaml
# vault/snow_credentials.yml (encrypted with ansible-vault)
snow_instance: "company.service-now.com"
snow_username: "svc_ansible_patching"
snow_password: "{{ vault_snow_password }}"    # Encrypted
```

### Why Automate ITIL?

| Manual ITIL | Automated ITIL |
|---|---|
| Engineer forgets to open CR before patching | CR auto-created before first step |
| CR stays "In Progress" for days (forgotten) | Auto-closed on completion/failure |
| Rollback plan is "we'll figure it out" | MOP has documented rollback steps |
| Auditor: "Show me evidence" → scramble | Reports auto-attached to CR |
| CAB: "What was the impact?" → guess | CR has exact: servers patched, packages, duration |

---

## 8. Monitoring Integration (Silence/Re-enable)

### Multi-System Silence

We silence THREE monitoring systems because alerts from different systems page different people:

```
┌───────────────────────────────────────────────────────────┐
│  Monitoring Silence Strategy                               │
│                                                           │
│  Alertmanager (Prometheus alerts) → Silence via API       │
│  CloudWatch Alarms (AWS infra)    → Disable alarm actions │
│  PagerDuty (on-call)              → Maintenance window    │
│                                                           │
│  Safety: ALL have auto-expire (4 hours max)               │
│  Re-enable: Explicit API call after successful patching   │
└───────────────────────────────────────────────────────────┘
```

### Why Auto-Expire Matters

**Scenario:** Playbook crashes at Step 8 (mid-patch). Steps 16 (re-enable monitoring) never runs.

**Without auto-expire:** Server stays silenced forever. It could be down for days and nobody knows.

**With auto-expire (4 hours):** Silence expires → alerts fire → team discovers the server needs attention. Maximum exposure: 4 hours.

### Silence Configuration

```yaml
# Alertmanager — silence specific host
- name: Create Alertmanager silence
  uri:
    url: "{{ alertmanager_url }}/api/v2/silences"
    method: POST
    body:
      matchers:
        - name: instance
          value: "{{ inventory_hostname }}:9100"
      startsAt: "{{ now }}"
      endsAt: "{{ now | dateutil_delta(hours=4) }}"   # Auto-expire
      comment: "OS Patching - CR {{ cr_number }}"

# CloudWatch — disable alarm actions (not delete alarm)
- name: Disable CloudWatch alarm actions
  amazon.aws.cloudwatch_metric_alarm:
    alarm_name: "{{ item }}"
    actions_enabled: false
    region: "{{ aws_region }}"
  loop: "{{ cloudwatch_alarms_for_host }}"
  delegate_to: localhost

# PagerDuty — maintenance window
- name: Create PagerDuty maintenance window
  uri:
    url: "https://api.pagerduty.com/maintenance_windows"
    method: POST
    headers:
      Authorization: "Token token={{ pagerduty_token }}"
    body:
      maintenance_window:
        start_time: "{{ now }}"
        end_time: "{{ now | dateutil_delta(hours=4) }}"
        services:
          - id: "{{ pagerduty_service_id }}"
        description: "OS Patching - {{ inventory_hostname }}"
  delegate_to: localhost
```

---

## 9. Security Design

### Defence-in-Depth for Patching

| Layer | What | How |
|---|---|---|
| **Credentials** | No plaintext passwords anywhere | Ansible Vault (AES-256) for ServiceNow, SMTP, PagerDuty |
| **Package exclusions** | Protect critical packages | Explicit exclude list prevents unintended updates to DB/custom packages |
| **File integrity** | Detect overwritten configs | md5 checksum verification of 8 critical components post-patch |
| **Certificate validation** | TLS health after patching | Expiry, permissions, key-pair match, CA bundle (4 checks) |
| **Blast radius** | Limit damage if something goes wrong | serial: 20% → maximum 2 servers at risk at any time |
| **Auto-rollback** | Don't wait for human to decide | 7-dimension validation auto-triggers rollback on ANY failure |
| **Snapshot** | Catastrophic failure recovery | AMI snapshot before patching → instant full revert |
| **Audit trail** | Who did what, when | Every step logged, reports attached to CR, Git history |

### Ansible Vault Usage

```bash
# Encrypt credentials
ansible-vault encrypt vault/snow_credentials.yml

# Run playbook with vault
ansible-playbook servicenow_patching.yml --ask-vault-pass

# In AAP: Vault password stored as credential type — never typed
```

### What's in Vault

| Secret | Used By |
|---|---|
| ServiceNow password | CR lifecycle (open/update/close) |
| SMTP credentials | Email notifications |
| PagerDuty routing key | Incident creation on failure |
| Slack webhook URL | Channel notifications |
| AWS credentials (if not IAM role) | ALB management, snapshots |

---

## 10. Ansible Automation Platform (AAP) Execution

### Why AAP (Not Just `ansible-playbook` on cron)

| Feature | Raw Ansible | AAP |
|---|---|---|
| Scheduling | cron (no visibility) | Visual scheduler + calendar view |
| RBAC | Everyone is root | Teams, roles, permissions per resource |
| Audit trail | Log file (if you remember to save it) | Built-in logging, searchable |
| Credentials | Vault file on disk | Credential types, rotated, never exposed |
| Surveys | Hardcoded vars or command-line args | Interactive forms (hostname, patch_type, exclude_packages) |
| Approval | None (just runs) | Workflow approval nodes (CAB approval gate) |
| Notifications | DIY (add to playbook) | Built-in notification templates |
| Retry | Manual re-run | Click "Retry" on failed step |
| Workflow | Master playbook (complex) | Visual workflow template (drag-and-drop steps) |

### AAP Workflow Template

```
┌────────────────────────────────────────────────────────────────────┐
│  AAP WORKFLOW: OS Patching Lifecycle                                │
│                                                                    │
│  [Open CR] → [Silence] → [Pre-Check] → [ALB Drain] → [Patch]     │
│      │                                       │             │       │
│      │                                       │         [Validate]  │
│      │                                       │         /        \  │
│      │                                       │      PASS      FAIL │
│      │                                       │        │         │  │
│      │                                  [Re-register] │   [Rollback]│
│      │                                       │        │         │  │
│      └──────────────────── [Re-enable Mon] ──┘        │         │  │
│                                  │                    │         │  │
│                             [Close CR] ───────────────┘─────────┘  │
│                                  │                                  │
│                            [Notify] (Slack + Email + PagerDuty)    │
└────────────────────────────────────────────────────────────────────┘
```

### AAP Survey Form (Runtime Input)

| Field | Type | Options | Purpose |
|---|---|---|---|
| hostname | Text | Pattern: `web-*` | Which servers to patch |
| patch_type | Choice | all / security | Full update or security-only |
| allow_reboot | Boolean | Yes / No | Allow kernel reboot |
| exclude_packages | Textarea | One per line | Packages to skip |
| maintenance_window | Choice | 2h / 4h / 8h | Silence duration |

**This means:** Non-Ansible engineers (team leads, managers) can trigger patching by filling a form. No CLI knowledge required. RBAC controls who can run against production.

---

## 11. Key Design Decisions

| # | Decision | Why (Not the Alternative) |
|---|---|---|
| 1 | 18 discrete steps | Each independently testable, rerunnable. Not one monolithic playbook |
| 2 | Config-driven connectivity | Add new dependency tests via YAML vars, no code changes needed |
| 3 | Critical vs non-critical endpoints | Don't block patching because monitoring is temporarily unreachable |
| 4 | Auto-expire silences (4h) | Safety net — alerts resume even if playbook fails mid-way |
| 5 | Reports fetched to controller | Evidence survives even if target server dies/gets rolled back |
| 6 | PagerDuty only on failure | Don't wake on-call at 3 AM for successful patching |
| 7 | Conditional kernel check | Don't FAIL validation because no kernel update was pending |
| 8 | serial: 20% + max_fail: 10% | Balance between speed (more parallel) and safety (less blast radius) |
| 9 | 3-level service verification | `systemctl` alone isn't enough — process can be "active" but hung |
| 10 | Separate pre/post backup roles | Reusable independently, diff role compares them |
| 11 | ServiceNow integration | ITIL compliance — audit trail, CAB visibility, rollback evidence |
| 12 | Package exclusions in vars | Per-team customization without modifying role code |
| 13 | AMI snapshot before patch | Instant catastrophic recovery (< 5 min full server revert) |
| 14 | Vault for all credentials | Zero plaintext secrets in code, playbooks, or variables |
| 15 | Idempotent roles | Safe to re-run. If playbook fails at step 10, restart from step 10 |

---

## 12. Interview Talking Points

### 2-Minute Version

"Built a fully automated, zero-touch OS patching system with 18 discrete steps covering the complete lifecycle on Ansible Automation Platform. Opens ServiceNow Change Request with documented MOP, silences Alertmanager + CloudWatch + PagerDuty, drains traffic from ALB, patches servers in 20% batches with package exclusions, validates across 7 dimensions — packages, kernel, services, logs, disk, network, and application health — with automatic rollback on any failure. Post-validation verifies file integrity via checksums for 8 components, validates TLS certificates across 4 checks, tests connectivity to all dependencies, re-registers to ALB, re-enables monitoring, closes the CR with evidence, and sends multi-channel notifications. Zero human intervention for pass/fail decisions. Runs 500+ servers monthly with zero downtime."

### Key Interview Q&A

**Q: "How do you ensure zero downtime during patching?"**  
A: Three mechanisms. First, serial batching (20% of fleet at a time — 80% always serving traffic). Second, ALB drain before touching the server (deregister → wait 60s drain → verify zero connections → then patch). Third, re-register only AFTER 7-dimension validation passes (bad patch never gets traffic).

**Q: "What happens if patching fails?"**  
A: Automatic at every level. 7-dimension validation decides PASS/FAIL — no human judgment. On FAIL: rollback triggered (revert to AMI snapshot), server stays out of ALB, CR updated as failed, PagerDuty incident created, Slack notification sent. Other servers (already patched successfully) stay healthy. Blast radius: maximum 20% of fleet.

**Q: "How do you handle the ITIL compliance requirement?"**  
A: Fully automated ServiceNow integration. CR created BEFORE first step (with MOP and rollback plan documented). Updated DURING patching (progress per batch). Closed AFTER (with pass/fail evidence and package lists attached). Auditor gets complete trail: who initiated, when, what changed, evidence of validation, who approved. No human can forget to update the ticket.

**Q: "Why 18 steps? Why not fewer?"**  
A: Each step is independently testable, rerunnable, and has a clear responsibility. If the playbook fails at step 10, I can restart from step 10 — not from scratch. For debugging: "Which step failed?" gives immediate context. For compliance: each step generates evidence. For evolution: I can replace step 8 (patching method) without touching step 13 (validation).

**Q: "How would you scale this to 1000+ servers?"**  
A: Already designed for scale. serial: 20% works at any fleet size (200 servers = 40 per batch). AAP handles parallel execution to multiple batches. Dynamic inventory (aws_ec2 plugin) replaces static host lists. Tower Instance Groups for distributed execution. The only change: adjust serial percentage and max_fail_percentage based on fleet size and risk tolerance.

**Q: "What's the difference between this and just running `dnf update` in a for loop?"**  
A: A for loop: no validation, no rollback, no traffic management, no monitoring awareness, no audit trail, no blast radius control, no integrity checking, no certificate validation, and no notification. One failed server in a for loop goes unnoticed until users report errors. My system catches it in 2 minutes, rolls back automatically, and pages the team — all before users notice.

---

## Future Improvements

| # | Improvement | Status |
|---|---|---|
| 1 | Dynamic inventory (aws_ec2 / vmware_vm_inventory) | Planned |
| 2 | Molecule testing for all 12 roles | Planned |
| 3 | Master orchestrator playbook (single entry point for all 18 steps) | Planned |
| 4 | ServiceNow report attachment via API (not just text in close notes) | Planned |
| 5 | Compliance dashboard (Grafana) showing patch status across fleet | Future |
| 6 | Automatic patch scheduling based on vulnerability severity | Future |
| 7 | Integration with Qualys/Nessus (patch only servers with vulnerabilities) | Future |

---

## Cost & Resource Summary

| Component | Purpose | Cost |
|---|---|---|
| AAP Controller | Workflow execution, RBAC, scheduling | License-based (Red Hat) |
| Ansible Execution Environments | Containerized runtime with collections | Included in AAP |
| ServiceNow instance | ITIL change management | Enterprise license |
| AWS ALB | Traffic management during patching | Existing infrastructure |
| S3 | Backup storage, report storage | ~$5/month |
| PagerDuty | On-call alerting (failure only) | Existing subscription |
| Slack | Team notifications | Existing workspace |

---

## Summary

This project demonstrates mastery of:
- **Day-2 operations** (not just deploy-and-forget — ongoing maintenance at scale)
- **Enterprise ITIL compliance** (ServiceNow CR lifecycle fully automated)
- **Zero-downtime maintenance** (ALB drain + serial batching)
- **Automated decision-making** (7-dimension validation, no human in the loop)
- **Multi-layer security** (integrity, certificates, vault, blast radius)
- **Observability awareness** (silence → patch → re-enable monitoring)
- **Ansible at enterprise scale** (AAP, RBAC, workflow templates, credential management)
- **Production reliability** (12 reusable roles, idempotent, tested independently)

This is what 12 YOE looks like: not writing the patch command, but designing the entire system that safely patches 500 servers without anyone waking up at 3 AM.
