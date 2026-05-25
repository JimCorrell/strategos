FROM python:3.12-slim

# libspatialindex is required by the rtree package (spatial index for combat range queries)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps before copying source so this layer is cached
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runtime data lives outside the image so it survives container restarts
ENV STRATEGOS_DB_PATH=/data/strategos.db
ENV STRATEGOS_CHECKPOINT_DIR=/data/checkpoints
ENV STRATEGOS_LOG_LEVEL=INFO

RUN mkdir -p /data/checkpoints

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/status')" || exit 1

CMD ["python", "-m", "uvicorn", "api:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--log-level", "warning"]
