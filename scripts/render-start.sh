#!/usr/bin/env bash
set -euo pipefail
python backend/manage.py migrate --noinput
python backend/manage.py bootstrap_deployment
exec gunicorn --chdir backend config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --threads 2 --timeout 60 --access-logfile - --error-logfile -
