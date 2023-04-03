#!/bin/bash

CONTAINER_NAME="cont-telegram-whisper-bot"
IMAGE_NAME="img-telegram-whisper-bot"

# Detect platform architecture
if uname -m | grep -qi 'arm'; then
  echo "Detected ARM architecture"
  DOCKERFILE=Dockerfile_arm
elif uname -m | grep -qi 'x86_64'; then
  echo "Detected x64 architecture"
  DOCKERFILE=Dockerfile
else
  echo "Unknown architecture: $ARCH"
  exit 1
fi


# Remove the container if it already exists
if docker ps -a --format '{{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
  docker stop $CONTAINER_NAME
  docker rm $CONTAINER_NAME
fi

# Build the Docker image with selected Dockerfile
docker build -t $IMAGE_NAME -f $DOCKERFILE .

docker run -d --name $CONTAINER_NAME --env-file .env $IMAGE_NAME
