# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.12

# ---------- builder : installe les dépendances dans un venv isolé
FROM python:${PYTHON_VERSION}-slim AS builder
ARG INSTALL_ML=1
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements/ /tmp/requirements/
RUN pip install -r /tmp/requirements/base.txt gunicorn==23.0.0 \
 && if [ "$INSTALL_ML" = "1" ]; then pip install -r /tmp/requirements/ml.txt; fi

# ---------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    HF_HOME=/var/cache/huggingface \
    MEDIA_ROOT=/app/media
RUN groupadd --system app && useradd --system --gid app --home /app app \
 && mkdir -p /app/media /app/staticfiles /var/cache/huggingface \
 && chown -R app:app /app /var/cache/huggingface
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app . .
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput
USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
