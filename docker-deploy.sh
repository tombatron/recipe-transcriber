#!/bin/bash
# Quick start script for Docker deployment

set -e

echo "=== Recipe Transcriber Docker Setup ==="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
    cat > .env << EOF
SECRET_KEY=${SECRET_KEY}
EOF
    echo "✓ Generated .env with random SECRET_KEY"
else
    echo "✓ .env file already exists"
fi

# Create directories
echo ""
echo "Creating required directories..."
mkdir -p data uploads redis-data
chmod 755 data uploads redis-data
echo "✓ Created data/, uploads/, and redis-data/ directories"

# Check if traefik network exists
echo ""
echo "Checking for Traefik network..."
if ! docker network inspect proxy &>/dev/null; then
    echo "⚠  Warning: 'proxy' Docker network not found"
    echo "   You may need to create it: docker network create proxy"
    echo "   Or adjust docker-compose.yml to use your existing Traefik network name"
else
    echo "✓ Traefik (proxy) network exists"
fi

# Build and start
echo ""
echo "Building Docker images..."
docker compose build

echo ""
echo "Starting services..."
docker compose up -d

echo ""
echo "=== Deployment Started ==="
echo ""
echo "Services starting up. Monitor progress with:"
echo "  docker compose logs -f"
echo ""
echo "Note: Ollama will download models on first run (~10-15 minutes)"
echo ""
echo "Check status:"
echo "  docker compose ps"
echo ""
echo "Once ready, your app will be available at:"
echo "  https://recipes.tombatron.dev"
echo ""
