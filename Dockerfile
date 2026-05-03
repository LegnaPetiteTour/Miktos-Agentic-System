# Miktos Web Cockpit — Dockerfile
#
# Build:  docker build -t miktos-cockpit .
# Run:    docker-compose up
#
# The container runs the FastAPI/uvicorn cockpit only.
# Background workers (coordinator, streamlab, etc.) are still launched by
# the operator via run_session.py on the host — they share the data/ volume.

FROM python:3.11-slim AS base

# System deps for Pillow + audio tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1-mesa-glx \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer-cache friendly)
COPY pyproject.toml ./
# Install only the runtime extras (no dev/test)
RUN pip install --no-cache-dir ".[runtime]" 2>/dev/null || \
    pip install --no-cache-dir \
        "fastapi>=0.111" \
        "uvicorn[standard]>=0.29" \
        "jinja2>=3.1" \
        "python-multipart>=0.0.9" \
        "pyyaml>=6.0" \
        "python-dotenv>=1.0.0" \
        "psutil>=5.9" \
        "Pillow>=10.0.0" \
        "piexif>=1.1.3" \
        "requests>=2.31" \
        "rich>=13.0" \
        "PyJWT>=2.8" \
        "cryptography>=42" \
        "pydantic>=2.0.0"

# Copy source
COPY engine/    ./engine/
COPY domains/   ./domains/
COPY web/       ./web/
COPY config/    ./config/
COPY scripts/   ./scripts/

# data/ is intentionally NOT copied — it is mounted as a volume at runtime
# so credentials and session files persist across container rebuilds.
RUN mkdir -p /app/data/state /app/data/logs /app/data/messages \
             /app/data/sessions /app/data/templates /app/data/review_queue

# Non-root user for security
RUN useradd -m -u 1001 miktos && chown -R miktos:miktos /app
USER miktos

EXPOSE 8000

# Health check — cockpit root should return 200
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health-check')" 2>/dev/null || exit 1

CMD ["python", "-m", "uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000"]
