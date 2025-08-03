FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install only essential system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with optimization
RUN pip install --no-cache-dir -r requirements.txt \    && pip cache purge

# Copy only necessary application code
COPY backend/ ./backend/
COPY scraper/ ./scraper/
COPY frontend/ ./frontend/
COPY config.py .
COPY runtime.txt .

# Create minimal directories
RUN mkdir -p logs /tmp/model_cache

# Set environment variables for Railway
ENV RAILWAY_ENVIRONMENT=production
ENV RAILWAY_MEMORY_LIMIT=4GB
ENV PYTHONPATH=/app

# Expose port
EXPOSE $PORT

# Start the application with Railway-optimized settings
CMD gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --max-requests 1000 --max-requests-jitter 100