# AI Research System Sandbox Container
# Minimal, isolated environment for executing proposal code safely

FROM python:3.11-slim

# Labels
LABEL maintainer="ORKASTRATOR"
LABEL description="Secure sandbox for AI proposal code execution"
LABEL version="1.0"

# Set working directory
WORKDIR /sandbox

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install minimal Python packages for code execution
RUN pip install --no-cache-dir \
    numpy \
    scipy \
    pytest \
    typing-extensions

# Create non-root user for sandbox execution
RUN useradd -m -s /bin/bash sandbox_user \
    && chown -R sandbox_user:sandbox_user /sandbox

# Security: Remove unnecessary tools
RUN rm -rf /usr/bin/wget /usr/bin/curl 2>/dev/null || true

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HOME=/sandbox

# Switch to non-root user
USER sandbox_user

# Default command (will be overridden)
CMD ["python3", "--version"]
