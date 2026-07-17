# =============================================================================
# MULTI-STAGE DOCKERFILE — Production Ready
# =============================================================================
# Why multi-stage?
# - Stage 1 (builder): installs dependencies (may need gcc, build tools)
# - Stage 2 (production): copies ONLY installed packages + app code
# - Build tools, pip, git NEVER ship to production
# - Result: ~900MB → ~150MB, smaller attack surface, faster deploys
# =============================================================================

# ---------------------------------------------------------------------------
# STAGE 1: BUILDER — Install dependencies here, then throw this stage away
# ---------------------------------------------------------------------------
FROM python:3.9-slim AS builder

# Install build dependencies only if needed (some pip packages need gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements FIRST — layer caching means deps only reinstall when
# requirements.txt changes, NOT on every code change (saves minutes per build)
COPY requirements.txt .

# Install to /root/.local so we can copy just the installed packages
RUN pip install --user --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# STAGE 2: PRODUCTION — Clean, minimal, secure
# ---------------------------------------------------------------------------
FROM python:3.9-slim

# Why python:3.9-slim instead of python:3.9?
# - python:3.9 = full Debian (~900MB) with compilers, docs, man pages
# - python:3.9-slim = minimal Debian (~120MB) with only Python runtime
# - No git, no gcc, no build tools = attacker can't use them

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH

WORKDIR /app

# Copy ONLY installed packages from builder stage (no pip, no gcc, no source)
COPY --from=builder /root/.local /root/.local

# Copy application code (use .dockerignore to exclude .git, __pycache__, .env)
COPY . .

# Create log directories
RUN mkdir -p /var/log/gunicorn /var/run/gunicorn

# Don't run as root — if container is exploited, attacker gets limited user
# USER 1001 commented out for now as gunicorn needs write to log dirs
# TODO: fix permissions and enable non-root user
# RUN chown -R 1001:1001 /app /var/log/gunicorn /var/run/gunicorn
# USER 1001

EXPOSE 8000

# Use exec form (JSON array) — signals (SIGTERM) reach gunicorn directly
# Shell form (/bin/sh -c) swallows signals = ungraceful shutdown in K8s
ENTRYPOINT ["gunicorn", \
    "--bind", "0.0.0.0:8000", \
    "--workers", "3", \
    "--access-logfile", "/var/log/gunicorn/access.log", \
    "--error-logfile", "/var/log/gunicorn/error.log", \
    "LearnEasyAI.wsgi"]
