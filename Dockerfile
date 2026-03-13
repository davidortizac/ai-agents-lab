# ── Base image ──────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ── Working directory ────────────────────────────────────────────────────────
WORKDIR /app

# ── Install dependencies ─────────────────────────────────────────────────────
# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy project files ───────────────────────────────────────────────────────
COPY .env .
COPY app/ ./app/

# Create volume mount points (will be overridden by docker-compose volumes)
RUN mkdir -p /app/workspace /app/memory

# ── Entry point ──────────────────────────────────────────────────────────────
# Run the agent from the app directory so relative imports resolve correctly
WORKDIR /app/app
CMD ["python", "agent.py"]
