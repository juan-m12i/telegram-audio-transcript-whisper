#!/bin/bash

# Deployment script for telegram-audio-transcript-whisper
# Follows the three-folder pattern:
#   - Local: Current directory (development)
#   - Remote Repo: ~/projects/telegram-audio-transcript-whisper/ (git operations)
#   - Remote Deploy: /home/ubuntu/deployments/telegram-audio-transcript-whisper/ (runtime, no git)

set -e  # Exit on error

# Configuration
SSH_ALIAS="lightsail"
SSH_USER="ubuntu"
REMOTE_REPO_DIR="~/projects/telegram-audio-transcript-whisper"
REMOTE_DEPLOY_DIR="/home/ubuntu/deployments/telegram-audio-transcript-whisper"
PROJECT_NAME="telegram-audio-transcript-whisper"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if SSH alias is configured
log_info "Testing SSH connection to $SSH_ALIAS..."
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_ALIAS" exit 2>/dev/null; then
    log_error "Cannot connect to $SSH_ALIAS. Please check your SSH configuration."
    exit 1
fi
log_info "✓ SSH connection successful"

log_info "Starting deployment to VPS..."

# Step 1: Stop Docker containers from both repo and deployment folders to prevent conflicts
log_info "Stopping Docker containers (if running)..."
# Use docker compose v2 (preferred) or fallback to docker-compose v1
COMPOSE_CMD="docker compose"
if ! ssh "$SSH_ALIAS" "command -v docker &> /dev/null && docker compose version &> /dev/null" 2>/dev/null; then
  COMPOSE_CMD="docker-compose"
fi
# Stop containers from deployment folder
ssh "$SSH_ALIAS" "if [ -d $REMOTE_DEPLOY_DIR ]; then cd $REMOTE_DEPLOY_DIR && $COMPOSE_CMD -f docker_compose.yml down 2>/dev/null || true; fi" 2>/dev/null || true
# Stop containers from repo folder (if they exist) to prevent conflicts
ssh "$SSH_ALIAS" "if [ -d \$HOME/projects/$PROJECT_NAME ]; then cd \$HOME/projects/$PROJECT_NAME && $COMPOSE_CMD -f docker_compose.yml down 2>/dev/null || true; fi" 2>/dev/null || true

# Step 2: Create deployment directory
log_info "Creating deployment directory: $REMOTE_DEPLOY_DIR"
ssh "$SSH_ALIAS" "mkdir -p $REMOTE_DEPLOY_DIR"

# Step 3: Copy files (excluding .git, venv, cache, etc.)
log_info "Copying runtime files to deployment directory..."

# Use rsync to copy files, excluding development-only files
# Suppress the "sending incremental file list" message for cleaner output
rsync -avz --delete --info=progress2 \
    --exclude='.git/' \
    --exclude='venv/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='.mypy_cache/' \
    --exclude='.pytest_cache/' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.pyd' \
    --exclude='.DS_Store' \
    --exclude='.idea/' \
    --exclude='audio_files/' \
    --exclude='*.log' \
    --exclude='*.env' \
    --exclude='.env' \
    --exclude='.cursor/' \
    --exclude='webapp/' \
    --exclude='AGENTS.md' \
    --exclude='ARCHITECTURE_REVIEW.md' \
    --exclude='LICENSE' \
    --exclude='README.md' \
    ./ "$SSH_ALIAS:$REMOTE_DEPLOY_DIR/"

log_info "Files copied successfully"

# Step 4: Ensure docker_compose_recreate.sh is executable
log_info "Setting permissions on deployment scripts..."
ssh "$SSH_ALIAS" "chmod +x $REMOTE_DEPLOY_DIR/docker_compose_recreate.sh"

# Step 5: Verify .env files exist (warn if missing)
# Note: .env files are excluded from rsync to preserve VPS-specific configurations
log_info "Checking for environment files (preserved from previous deployment)..."
ENV_FILES=("gpt_whisper_bot.env" "notes_bot.env" "dev_bot.env" "sleep_bot.env" "workout_bot.env")
for env_file in "${ENV_FILES[@]}"; do
    if ssh "$SSH_ALIAS" "test -f $REMOTE_DEPLOY_DIR/$env_file"; then
        log_info "✓ Found $env_file (preserved)"
    else
        log_warn "⚠ $env_file not found in deployment directory. Make sure to create it manually with correct bot tokens."
    fi
done

# Step 6: Recreate Docker containers
log_info "Recreating Docker containers..."
ssh "$SSH_ALIAS" "cd $REMOTE_DEPLOY_DIR && ./docker_compose_recreate.sh"

# Step 7: Verify containers are running
log_info "Verifying containers are running..."
CONTAINERS=("cont-telegram-whisper-bot" "cont-telegram-notes-bot" "cont-telegram-dev-bot" "cont-telegram-sleep-bot" "cont-telegram-workout-bot")
for container in "${CONTAINERS[@]}"; do
    if ssh "$SSH_ALIAS" "docker ps --format '{{.Names}}' | grep -q '^$container$'"; then
        log_info "✓ $container is running"
    else
        log_warn "✗ $container is not running"
    fi
done

log_info "Deployment completed!"
log_info "Deployment directory: $REMOTE_DEPLOY_DIR"
log_info "To check container status: ssh $SSH_ALIAS 'cd $REMOTE_DEPLOY_DIR && $COMPOSE_CMD -f docker_compose.yml ps'"
log_info "To view logs: ssh $SSH_ALIAS 'cd $REMOTE_DEPLOY_DIR && $COMPOSE_CMD -f docker_compose.yml logs -f'"

