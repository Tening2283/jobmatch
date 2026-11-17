#!/bin/sh
# Déploiement sur le VPS avec rollback automatique si le healthcheck échoue.
# Usage : sh scripts/deploy.sh ghcr.io/owner/jobmatch:sha-xxxx
set -eu

NEW_IMAGE="$1"
COMPOSE="docker compose -f docker-compose.prod.yml"
STATE_FILE=".current_image"
PREVIOUS_IMAGE="$(cat "$STATE_FILE" 2>/dev/null || true)"

deploy() {
  export IMAGE="$1"
  $COMPOSE pull web worker beat
  $COMPOSE up -d db redis
  $COMPOSE run --rm web migrate
  $COMPOSE up -d --remove-orphans
}

healthy() {
  for _ in $(seq 1 30); do
    if $COMPOSE exec -T web python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health/').status==200 else 1)" 2>/dev/null; then
      return 0
    fi
    sleep 4
  done
  return 1
}

echo ">> Déploiement de $NEW_IMAGE"
deploy "$NEW_IMAGE"

if healthy; then
  echo "$NEW_IMAGE" > "$STATE_FILE"
  docker image prune -f >/dev/null
  echo ">> Déploiement réussi"
else
  echo "!! Healthcheck en échec" >&2
  if [ -n "$PREVIOUS_IMAGE" ]; then
    echo "!! Rollback vers $PREVIOUS_IMAGE" >&2
    export IMAGE="$PREVIOUS_IMAGE"
    $COMPOSE up -d --remove-orphans
  fi
  exit 1
fi
