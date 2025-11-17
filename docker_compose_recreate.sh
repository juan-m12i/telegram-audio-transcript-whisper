#!/bin/bash

DOCKER_COMPOSE_FILE="docker_compose.yml"

if [ "$#" -eq 0 ]; then
  echo "No specific containers provided. Recreating all containers..."
  # docker-compose down may show a harmless warning if network doesn't exist, but it handles it gracefully
  docker-compose -f "$DOCKER_COMPOSE_FILE" down || true
  docker-compose -f "$DOCKER_COMPOSE_FILE" build
  docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --force-recreate
else
  echo "Recreating specified containers: $@"
  for SERVICE in "$@"; do
    echo "Recreating $SERVICE..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" stop "$SERVICE"
    docker-compose -f "$DOCKER_COMPOSE_FILE" rm -f "$SERVICE"
    docker-compose -f "$DOCKER_COMPOSE_FILE" build "$SERVICE"
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --force-recreate "$SERVICE"
  done
fi
