FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and config
COPY src/ src/
COPY .env .
COPY vertex-key.json .

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8080
# Ensure stdout shows up in logs
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "src.api:api", "--host", "0.0.0.0", "--port", "8080"]
