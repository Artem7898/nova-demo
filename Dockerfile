FROM ghcr.io/astral-sh/uv:0.12.15 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --all-extras --no-dev --no-install-project && uv cache clean

COPY catalog ./catalog
COPY config ./config
COPY locale ./locale
COPY static ./static
COPY templates ./templates
COPY deploy ./deploy
COPY manage.py ./
ENV PATH="/app/.venv/bin:$PATH"
# Static collection needs neither a production secret nor a mounted database.
RUN DJANGO_SETTINGS_MODULE=config.settings DJANGO_DEBUG=1 python manage.py collectstatic --noinput
ENV DJANGO_SETTINGS_MODULE=config.railway_settings DJANGO_DEBUG=0
CMD ["sh", "deploy/start.sh"]
