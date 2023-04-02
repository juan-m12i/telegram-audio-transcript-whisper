#!/bin/bash

CONTAINER_NAME="cont-telegram-whisper-bot"
IMAGE_NAME="img-telegram-whisper-bot"

# Remove the container if it already exists
if docker ps -a --format '{{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
  docker stop $CONTAINER_NAME
  docker rm $CONTAINER_NAME
fi

# Build the Docker image
docker build -t $IMAGE_NAME .

docker run -d --name $CONTAINER_NAME --env-file .env $IMAGE_NAME
