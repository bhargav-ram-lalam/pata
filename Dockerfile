# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Final Runtime
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -g 10001 pata && \
    useradd -u 10001 -g pata -s /bin/bash -m patauser

# Install runtime curl for container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed wheels from builder
COPY --from=builder /root/.local /home/patauser/.local
ENV PATH=/home/patauser/.local/bin:$PATH

# Create persistent data and cache directories
RUN mkdir -p /app/data /home/patauser/.cache && \
    chown -R patauser:pata /app /home/patauser

# Copy application source code
COPY --chown=patauser:pata . /app

USER 10001

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATA_DATABASE_URL=sqlite:///./data/pata.db \
    HF_HOME=/home/patauser/.cache/huggingface \
    BHARATADDRESS_CACHE=/home/patauser/.cache/bharataddress

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health/live || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
