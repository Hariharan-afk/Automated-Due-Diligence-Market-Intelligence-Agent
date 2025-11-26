# ---------- Base image ----------
FROM python:3.10-slim AS base

# Avoid Python buffering and .pyc clutter
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system deps you actually need (qdrant client, curl for health checks, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# ---------- Install Python dependencies ----------
# Copy only requirements first for better layer caching
COPY requirements.txt .

# Install CPU-only torch first to avoid downloading huge CUDA wheels
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

# ---------- Copy project code ----------
# Copy src directory
COPY src/ ./src/


# Add project root to PYTHONPATH
ENV PYTHONPATH=/app

# Default command
CMD ["python", "src/main.py"]
