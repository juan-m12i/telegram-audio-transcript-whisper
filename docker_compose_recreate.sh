#!/bin/bash

DOCKER_COMPOSE_FILE="docker_compose.yml"

# Use docker compose v2 (without hyphen) which is more reliable and doesn't depend on Python/urllib3
# Falls back to docker-compose v1 if v2 is not available
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
  DOCKER_COMPOSE_CMD="docker compose"
else
  DOCKER_COMPOSE_CMD="docker-compose"
fi

if [ "$#" -eq 0 ]; then
  echo "No specific containers provided. Recreating all containers..."
  # docker compose down may show a harmless warning if network doesn't exist, but it handles it gracefully
  $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" down || true
  $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" build
  $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d --force-recreate
else
  echo "Recreating specified containers: $@"
  for SERVICE in "$@"; do
    echo "Recreating $SERVICE..."
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" stop "$SERVICE"
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" rm -f "$SERVICE"
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" build "$SERVICE"
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d --force-recreate "$SERVICE"
  done
fi
