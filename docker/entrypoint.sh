#!/bin/sh
set -e

wait_for_db() {
  python - <<'PY'
import os, sys, time
import django
django.setup()
from django.db import connection
for attempt in range(60):
    try:
        connection.ensure_connection()
        sys.exit(0)
    except Exception as exc:
        print(f"DB indisponible ({exc}), nouvel essai...", flush=True)
        time.sleep(1)
sys.exit("Base de données injoignable")
PY
}

case "$1" in
  web)
    wait_for_db
    if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then python manage.py migrate --noinput; fi
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --access-logfile -
    ;;
  worker)
    wait_for_db
    exec celery -A config worker --loglevel="${LOG_LEVEL:-info}" --concurrency="${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    wait_for_db
    exec celery -A config beat --loglevel="${LOG_LEVEL:-info}" --schedule /tmp/celerybeat-schedule
    ;;
  migrate)
    wait_for_db
    exec python manage.py migrate --noinput
    ;;
  *)
    exec "$@"
    ;;
esac
