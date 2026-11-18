# Multi-stage Dockerfile for Awardline deployment

FROM node:18-slim AS node-deps
WORKDIR /app
COPY package*.json ./
RUN npm install

FROM python:3.11-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Node dependencies from previous stage
COPY --from=node-deps /app/node_modules ./node_modules

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

# Copy application code
COPY . .

# Create runtime directories
RUN mkdir -p runtime/flags runtime/drafts runtime/approvals filings logs data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start the web application
CMD ["gunicorn", "web.app:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--timeout", "300"]
