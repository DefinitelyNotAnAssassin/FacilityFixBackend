FROM python:3.11-slim

WORKDIR /app

# Install system dependencies in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy and install Python dependencies
COPY requirements.txt .
# Install PyTorch CPU version first from the official index
    RUN pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
    # Increase pip network timeout to avoid transient ReadTimeoutErrors during docker build
    ENV PIP_DEFAULT_TIMEOUT=120
    # Retry once if the first pip install fails (helps with intermittent network timeouts)
    RUN pip install --no-cache-dir -r requirements.txt --timeout 120 || (sleep 5 && pip install --no-cache-dir -r requirements.txt --timeout 120)

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Use uvicorn with workers for better performance
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]