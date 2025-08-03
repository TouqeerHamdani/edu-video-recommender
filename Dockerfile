FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs and model cache directories
RUN mkdir -p logs /tmp/model_cache

# Set environment variables for Railway
ENV RAILWAY_ENVIRONMENT=production
ENV RAILWAY_MEMORY_LIMIT=4GB

# Expose port
EXPOSE $PORT

# Start the application with Railway-optimized settings
CMD gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --max-requests 1000 --max-requests-jitter 100 