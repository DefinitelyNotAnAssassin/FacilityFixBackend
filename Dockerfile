FROM python:3.11-slim

WORKDIR /app

# Install system dependencies in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

# Copy and install Python dependencies
COPY requirements.txt .

# Install PyTorch CPU version first from the official index
RUN pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu

# Retry once if the first pip install fails (helps with intermittent network timeouts)
RUN pip install --no-cache-dir -r requirements.txt --timeout 120 || (sleep 5 && pip install --no-cache-dir -r requirements.txt --timeout 120)

# Copy application code
COPY . .

# Copy ML models into the image
COPY app/models/facilityfix-ai ./app/models/facilityfix-ai

# Verify models were copied
RUN ls -la app/models/facilityfix-ai/

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Use uvicorn with workers for production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]