# ============================================================================
# Stage 1: Build dependencies
# ============================================================================
FROM python:3.13-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================================
# Stage 2: Lean runtime
# ============================================================================
FROM python:3.13-slim

# Python optimizations
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2

WORKDIR /app

# Install system dependencies for healthcheck and process management
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy only installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY sources/ ./sources/
COPY admin/ ./admin/
COPY agent.py server.py threads.py clients.py ./
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY settings.json* ./

# Runtime setup
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app && \
    chmod 755 /app/data

USER appuser

EXPOSE 4500

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD ["wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:4500/health"]

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "4500", \
     "--loop", "uvloop", "--http", "httptools", \
     "--limit-concurrency", "100", "--backlog", "128", \
     "--timeout-keep-alive", "65", "--timeout-graceful-shutdown", "10", \
     "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
