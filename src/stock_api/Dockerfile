# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Jakarta

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    tzdata \
    && ln -snf /usr/share/zoneinfo/Asia/Jakarta /etc/localtime \
    && echo "Asia/Jakarta" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY stock_api/requirements.txt .

# Install Python dependencies
# First, install critical dependencies to avoid version conflicts
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    python -c "import marshmallow; print(marshmallow.__version__)" && \
    python -c "import environs; print('environs OK')"


# Verify pymilvus can import correctly
RUN python -c "from pymilvus import connections, Collection; print('PyMilvus imported successfully')"

# Copy helper modules (news pipeline integration)
# These modules provide scraping, RAG indexing, and query functionality
COPY helper /app/helper

# Copy application code
COPY stock_api/stock_api_server.py .

# Expose port
EXPOSE 13052

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:13052/')" || exit 1

# Run the application
# Note: Override host to 0.0.0.0 to accept connections from outside container
CMD ["uvicorn", "stock_api_server:app", "--host", "0.0.0.0", "--port", "13052"]
