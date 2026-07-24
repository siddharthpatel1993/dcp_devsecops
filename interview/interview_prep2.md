# Interview Prep 2 — Follow-Up Q&A (From Study Sessions)

---

## Kubernetes

### Q: What is a StatefulSet and how is it different from a Deployment?

**Answer:**

Deployment = stateless. Pods get random names, are interchangeable, no fixed identity.
StatefulSet = stateful. Pods get fixed ordered names, each has its own persistent volume, stable network identity.

| | Deployment | StatefulSet |
|---|---|---|
| Pod names | Random (app-xk2mq) | Fixed, ordered (mysql-0, mysql-1) |
| Startup order | All at once (parallel) | One by one (0 → 1 → 2) |
| Storage | Shared or none | Each pod gets its OWN persistent volume |
| Network identity | No stable hostname | Stable DNS: `mysql-0.mysql-svc.namespace` |
| Use case | Web apps, APIs (stateless) | Databases, Kafka, Redis (stateful) |
| Pod replacement | New random pod | Same name, same volume reattached |

**Why fixed name matters:** MySQL replication — mysql-0 is PRIMARY, mysql-1 and mysql-2 are REPLICAS following mysql-0. If primary dies and comes back with random name → replicas don't know who to follow. With StatefulSet → comes back as mysql-0 → replicas reconnect automatically.

**Interview one-liner:** "Deployment for stateless (interchangeable pods). StatefulSet for stateful (fixed names, ordered startup, each pod gets its own persistent volume). Used for databases, Kafka, anything needing stable identity."

---

## Docker

### Q: How do you create a multi-stage Docker build? Why use it?

**Answer:**

You're correct. Two stages:

**Stage 1 (Builder):** Import base image → install ALL dependencies (pip packages, gcc compiler, build tools like curl, netstat). This image is fat/heavy.

**Stage 2 (Production):** Fresh slim image → copy ONLY the installed packages from builder (`/root/.local`) → copy app code → set user → define entrypoint. No build tools, no compiler, no pip.

```dockerfile
# Stage 1: Builder (heavy — has gcc, pip, build tools)
FROM python:3.9-slim AS builder
RUN apt-get update && apt-get install -y gcc curl
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Production (light — only runtime)
FROM python:3.9-slim
COPY --from=builder /root/.local /root/.local    # Only installed packages
COPY . .                                          # App code
USER 1001                                         # Non-root
ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8000", "app.wsgi"]
```

**Result:**
- Builder image: ~900MB (gcc, pip, headers, wheels)
- Final image: ~150MB (only Python runtime + packages + your code)

**Why smaller is better:**
1. **Security** — attacker compromises container → no gcc, no curl, no wget to download exploits
2. **Speed** — smaller image = faster pull = faster deployments
3. **Fewer CVEs** — less packages = fewer vulnerabilities in Trivy scan
4. **Cost** — less storage in registry

**Interview one-liner:** "Builder stage installs everything (compiler, deps, tools). Production stage copies ONLY the installed packages from builder — no build tools, no compiler. Result: 900MB → 150MB, smaller attack surface, fewer CVEs."

---
