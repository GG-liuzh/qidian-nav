ARG NODE_IMAGE=node:24-alpine
ARG PYTHON_IMAGE=python:3.12-slim-bookworm

FROM ${NODE_IMAGE} AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 qidiannav \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin qidiannav
COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.1 setuptools==84.0.0 \
    && python -m pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /build/dist/ ./frontend/dist/
RUN install -d -o qidiannav -g qidiannav -m 0700 /app/.runtime
USER 10001:10001
WORKDIR /app/backend
EXPOSE 4173
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4173/api/v1/health', timeout=3)"]
CMD ["python", "-m", "app.cli", "serve", "--host", "0.0.0.0", "--port", "4173"]
