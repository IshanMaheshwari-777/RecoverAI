# syntax=docker/dockerfile:1

# --- stage 1: build the dashboard -----------------------------------------
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build   # vite emits to ../src/recover_ai/api/static

# --- stage 2: the app ---------------------------------------------------
FROM python:3.12-slim AS app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RECOVERY_LOG_JSON=true \
    RECOVERY_DATA_DIR=/data

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# built dashboard from stage 1
COPY --from=web /src/recover_ai/api/static/ ./src/recover_ai/api/static/

RUN useradd -u 10001 -m app && mkdir -p /data && chown -R app /data /app
USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health').status==200 else 1)"

CMD ["uvicorn", "recover_ai.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
