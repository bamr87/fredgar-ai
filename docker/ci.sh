#!/bin/sh
set -e
export PYTHONPATH=/app/src
export DJANGO_SETTINGS_MODULE=config.settings_test
cd /app
ruff check src tests
python src/manage.py makemigrations --check --dry-run
python src/manage.py check
pytest -q \
  --cov=warehouse --cov=config --cov=sec_edgar --cov=public_data \
  --cov=api --cov=enrichment \
  --cov-report=term-missing \
  --cov-fail-under=50
