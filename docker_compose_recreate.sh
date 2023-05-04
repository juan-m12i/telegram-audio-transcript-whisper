#!/bin/bash
DOCKER_COMPOSE_FILE="docker_compose.yml"

#docker stop cont-telegram-whisper-bot
#docker rm cont-telegram-whisper-bot


docker-compose -f "$DOCKER_COMPOSE_FILE" down
docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
