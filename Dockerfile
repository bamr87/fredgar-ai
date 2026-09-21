# API server (run from repo root: docker build -t fredgar-ai .)
# Stages: base -> test (CI image) -> runtime (default for compose web)
FROM python:3.14-slim-trixie AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/

FROM base AS test

COPY requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt

COPY tests/ /app/tests/
COPY pyproject.toml /app/

# Reference JSON used by sec_edgar.reference_data (tests and runtime)
COPY data/reference /app/data/reference

COPY docker/ci.sh /app/docker-ci.sh
RUN chmod +x /app/docker-ci.sh

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV DJANGO_SETTINGS_MODULE=config.settings_test

CMD ["/app/docker-ci.sh"]

FROM base AS runtime

COPY data/reference /app/data/reference

COPY docker/entrypoint-web.sh /entrypoint-web.sh
RUN chmod +x /entrypoint-web.sh

# Run as a non-root user (uid 1000); ensure the data dir is writable for HTM downloads.
RUN useradd --uid 1000 --create-home --shell /bin/bash appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

# Worker count is tunable via GUNICORN_WORKERS (see entrypoint -> WEB_CONCURRENCY).
ENV GUNICORN_WORKERS=2

WORKDIR /app/src

EXPOSE 8000
ENTRYPOINT ["/entrypoint-web.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
