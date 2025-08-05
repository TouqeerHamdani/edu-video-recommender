FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY scraper/ ./scraper/
COPY frontend/ ./frontend/
COPY config.py .

# Create directories
RUN mkdir -p logs /tmp/model_cache

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=10000

# Expose port
EXPOSE $PORT

# Start the application
CMD gunicorn backend.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --timeout 120 \
    --preload