# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
COPY . .
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Worker image adds headless Chromium for Scrapy-Playwright.
FROM base AS worker
USER root
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium && chmod -R a+rX /ms-playwright
USER appuser
