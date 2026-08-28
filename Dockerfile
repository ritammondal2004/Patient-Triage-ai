
FROM python:3.13-slim

WORKDIR /app

# Build deps for psycopg2-binary + curl for health check, then clean up
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user for production hardening
RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000


HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", "--timeout", "120", "app.main:app"]
