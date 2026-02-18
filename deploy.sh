#!/bin/bash
# DPLUS Dashboard - Quick Deploy Script
# Run this script to deploy the dashboard on any Docker-enabled server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="dplus-dashboard"
CONTAINER_NAME="dplus-dashboard"
DEFAULT_PORT=8501

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  DPLUS Dashboard Quick Deploy${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${YELLOW}Warning: Docker Compose not found, using standalone Docker${NC}"
    COMPOSE_CMD=""
fi

# Prompt for configuration
read -p "Enter port number (default: $DEFAULT_PORT): " PORT
PORT=${PORT:-$DEFAULT_PORT}

read -p "Enter custom password (press Enter for default 'dplus2024'): " CUSTOM_PASSWORD

# Create .env file
if [ -n "$CUSTOM_PASSWORD" ]; then
    PASSWORD_HASH=$(echo -n "$CUSTOM_PASSWORD" | sha1sum | cut -d' ' -f1)
    cat > .env << EOF
DASHBOARD_PORT=$PORT
APP_PASSWORD=$CUSTOM_PASSWORD
APP_PASSWORD_HASH=$PASSWORD_HASH
EOF
    echo -e "${GREEN}✓ Custom password configured${NC}"
else
    cat > .env << EOF
DASHBOARD_PORT=$PORT
EOF
    echo -e "${YELLOW}Using default password: dplus2024${NC}"
fi

# Create data directories
mkdir -p data/uploaded
echo -e "${GREEN}✓ Data directories created${NC}"

# Build and deploy
echo ""
echo -e "${GREEN}Building Docker image...${NC}"
if [ -n "$COMPOSE_CMD" ]; then
    $COMPOSE_CMD build
    echo -e "${GREEN}Starting containers...${NC}"
    $COMPOSE_CMD up -d
    echo -e "${GREEN}✓ Deployed with Docker Compose${NC}"
else
    docker build -t $IMAGE_NAME .
    # Stop existing container if running
    if [ $(docker ps -aq -f name=$CONTAINER_NAME) ]; then
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true
    fi
    docker run -d \
        --name $CONTAINER_NAME \
        --restart unless-stopped \
        -p $PORT:8501 \
        -v $(pwd)/data:/app/data \
        $IMAGE_NAME
    echo -e "${GREEN}✓ Deployed with Docker${NC}"
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "Dashboard URL: ${GREEN}http://localhost:$PORT${NC}"
echo -e "Password: ${YELLOW}${CUSTOM_PASSWORD:-dplus2024}${NC}"
echo ""
echo "Useful commands:"
echo "  View logs:   docker logs -f $CONTAINER_NAME"
echo "  Stop:        docker stop $CONTAINER_NAME"
echo "  Restart:     docker restart $CONTAINER_NAME"
echo ""
