#!/bin/sh
set -eu

export DJANGO_SETTINGS_MODULE=config.railway_settings
export DJANGO_DEBUG=0

# Volumes exist at runtime, not in the build or a Railway pre-deploy command.
python -c 'from django.conf import settings; settings.DATA_DIR.mkdir(parents=True, exist_ok=True)'
python manage.py migrate --noinput

# Lab scenarios use process-local state: keep exactly one synchronous worker.
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 --threads 1 --timeout 60 \
  --access-logfile - --error-logfile -
