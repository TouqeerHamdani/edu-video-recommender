# Multi-stage build to reduce final image size
FROM python:3.9-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies in virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Final stage - minimal runtime image
FROM python:3.9-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    libffi6 \
    libssl1.1 \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy only necessary application code
COPY backend/ ./backend/
COPY scraper/ ./scraper/
COPY frontend/ ./frontend/
COPY config.py .

# Create minimal directories and set permissions
RUN mkdir -p logs /tmp/model_cache && chown -R appuser:appuser /app

# Set environment variables for Railway
ENV RAILWAY_ENVIRONMENT=production
ENV RAILWAY_MEMORY_LIMIT=4GB
ENV PYTHONPATH=/app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE $PORT

# Start the application with Railway-optimized settings
CMD gunicorn backend.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --preload \
    --graceful-timeout 30 \
    --keep-alive 2