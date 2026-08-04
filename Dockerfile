FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY templates/ ./templates/
COPY static/ ./static/

RUN pip wheel --wheel-dir /wheels .

FROM python:3.11-slim

LABEL org.opencontainers.image.title="Find My Timeline"
LABEL org.opencontainers.image.description="Store and display historical Apple Find My device locations"
LABEL org.opencontainers.image.source="https://github.com/heckpiet/find-my-timeline-unraid"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=5000 \
    DATABASE_PATH=/app/data/locations.db

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels find-my-timeline && rm -rf /wheels

VOLUME ["/root/.find-my-timeline", "/app/data"]
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health/ready', timeout=3)" || exit 1

CMD ["find-my-timeline", "start"]
