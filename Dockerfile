FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build
FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends g++ cmake make && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-dev.txt ./
RUN python -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements-dev.txt
COPY CMakeLists.txt Makefile pyproject.toml ./
COPY src/ src/
COPY tests/ tests/
COPY proto/ proto/
COPY sdk/ sdk/
COPY scripts/ scripts/
RUN make build proto && useradd -u 10001 -m atlas && mkdir -p .cache docs/results && chown -R atlas:atlas /app
COPY --from=web /web/dist apps/web/dist/
COPY docs/results/*-*.json docs/results/
USER 10001
ENV PYTHONPATH=build:sdk ATLAS_HOST=0.0.0.0 PORT=8094
EXPOSE 8094
CMD [".venv/bin/python", "scripts/server.py"]
