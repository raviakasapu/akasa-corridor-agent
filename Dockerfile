FROM python:3.11-slim

WORKDIR /app

# Install git for cloning private repos
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY app/ app/
COPY configs/ configs/

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install dependencies
RUN pip install --no-cache-dir .

# Install private git dependency (GITHUB_TOKEN passed as build arg)
# FRAMEWORK_VERSION arg busts cache - change value to force re-fetch
ARG GITHUB_TOKEN
ARG FRAMEWORK_VERSION=1
RUN pip install --no-cache-dir "git+https://${GITHUB_TOKEN}@github.com/raviakasapu/auto-ai-agent-framework.git@main#subdirectory=agent-framework-pypi"

# Expose port (Railway sets PORT dynamically)
EXPOSE 8052

# Worker configuration environment variables
ENV WORKERS=5 \
    CONCURRENCY_LIMIT=100 \
    BACKLOG=2048

# Start command - use shell form to expand environment variables
CMD uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8052} \
    --workers ${WORKERS:-5} \
    --limit-concurrency ${CONCURRENCY_LIMIT:-100} \
    --backlog ${BACKLOG:-2048}
