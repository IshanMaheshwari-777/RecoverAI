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
    PORT=8000

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
# built dashboard from stage 1 — copied in before install so hatchling
# bundles it into the wheel (see [tool.hatch...artifacts] in pyproject.toml)
COPY --from=web /src/recover_ai/api/static/ ./src/recover_ai/api/static/
RUN pip install --no-cache-dir .

# bake a deterministic demo report so the hosted dashboard has data on first
# load. No credentials at build time -> fully simulated links + deterministic
# fallback diagnosis: zero external calls, zero cost. A deploy with real keys
# can re-run from the dashboard.
RUN recover-ai run --count 180 --seed 42 --quiet

RUN useradd -u 10001 -m app && chown -R app /app
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD sh -c 'python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen(sys.argv[1]).status==200 else 1)" "http://localhost:${PORT:-8000}/api/health"'

# honour $PORT (Render / Railway / Hugging Face inject it); default 8000
CMD ["sh", "-c", "uvicorn recover_ai.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
