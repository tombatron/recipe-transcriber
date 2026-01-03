# Recipe Transcriber - Docker Deployment Guide

This guide covers deploying the Recipe Transcriber app using Docker Compose (v2 `docker compose`) with an external Traefik reverse proxy.

## Architecture

- **web**: Flask app (Gunicorn with gevent workers for WebSocket support)
- **worker**: Celery worker for async recipe transcription (standalone, no Flask app context)
- **redis**: Message broker for Celery + WebSocket coordination for Turbo Streams
- **ollama**: Local LLM server with vision models

The worker communicates with Flask via HTTP webhooks to trigger real-time Turbo Stream updates.

## Prerequisites

1. Docker with Compose plugin installed (`docker compose`)
2. External Traefik instance running with:
   - Network named `proxy`
   - Let's Encrypt or other cert resolver (e.g., `route53` for AWS Route53)
   - `https` entrypoint (port 443)
3. DNS: Your domain (e.g., `recipes.example.com`) → your server IP

## Initial Setup

### 1. Clone and Prepare

```bash
cd /home/tombatron/projects/receipe-transcriber
```

**Note:** Ensure your Traefik is running with a network named `proxy` before starting services.

### 2. Create Required Directories

```bash
mkdir -p data uploads redis-data
chmod 755 data uploads redis-data
```

### 3. Set Environment Variables

Create a `.env` file:

```bash
cat > .env << 'EOF'
SECRET_KEY=your-super-secret-key-change-me
DOMAIN=recipes.example.com
EOF
```

Update values:
1. Generate a secure SECRET_KEY:
```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

2. Set your actual domain name:
```bash
DOMAIN=your-actual-domain.com
```

### 4. Build and Start Services

```bash
# Build the app image
docker compose build

# Start all services
docker compose up -d

# Check logs
docker compose logs -f
```

### 5. Verify Ollama Models

The `ollama` service pre-pulls models on first startup. This takes time. Monitor:

```bash
docker compose logs -f ollama
```

Once you see "qwen3-vl" and "llama3.2" pulled, the service is ready.

### 6. Database Migration

The `web` service runs `flask db upgrade` on startup automatically.

To manually run migrations:

```bash
docker compose exec web flask db upgrade
```

## Updating the Deployment

### Update Application Code

```bash
# Pull latest code
git pull

# Rebuild and restart
# Pull latest code
git pull

# Rebuild and restart
docker compose build web worker
docker compose up -d
```

### Update Domain or Traefik Labels

Edit your `.env` file:

```bash
DOMAIN=new-domain.com
```

Then restart:

```bash
docker compose up -d web
```

Note: The domain is configured via the `DOMAIN` environment variable in `.env`, not hardcoded in `docker-compose.yml`.

### Change Ollama Models

Edit environment in `docker-compose.yml`:

```yaml
environment:
  - OLLAMA_VISION_MODEL=llava  # Change model
```

Also update the `ollama.command` to pull the new model:

```yaml
command:
  - |
    /bin/ollama serve &
    sleep 10
    ollama pull llava
    ollama pull llama3.2
    wait
```

Recreate services:

```bash
docker compose up -d --force-recreate ollama web worker
```

### Update Python Dependencies

Edit `pyproject.toml`, then:

```bash
docker compose build --no-cache
docker compose up -d
```

### Scale Celery Workers

```bash
docker compose up -d --scale worker=4
```

Or edit `docker-compose.yml`:

```yaml
worker:
  deploy:
    replicas: 4
```

## Database Migrations

### Create New Migration

```bash
docker compose exec web flask db migrate -m "description"
```

### Apply Migration

```bash
docker compose exec web flask db upgrade
```

### Rollback Migration

```bash
docker compose exec web flask db downgrade
```

## Traefik Configuration Notes

Your external Traefik must have:

### Network

Ensure the `proxy` network exists (created by your Traefik instance):

```bash
docker network inspect proxy
```

If not found, create it:

```bash
docker network create proxy
```

### Certificate Resolver

Update the compose labels if your cert resolver name differs from `route53`. Check your Traefik config

In your Traefik config (static):

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: your-email@example.com
      storage: /acme.json
      httpChallenge:
        entryPoint: web
```

### Entrypoint

```yaml
entryPoints:
  websecure:
    address: ":443"
```

## Persistent Data

Data is stored in:

- `./data/receipe.db` - SQLite database
- `./uploads/` - Uploaded recipe images
- `./redis-data/` - Redis AOF persistence file (`appendonly.aof`)
- Docker volumes: `ollama-data`

### Backup Database

```bash
cp data/receipe.db data/receipe.db.backup-$(date +%Y%m%d)
```

### Restore Database

```bash
docker-compose down
cp data/receipe.db.backup-YYYYMMDD data/receipe.db
docker-compose up -d
```

## Monitoring

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f ollama
```

### Check Service Health

```bash
docker compose ps
```

### Redis Connection

```bash
docker compose exec redis redis-cli ping
```

### Ollama Models

```bash
docker compose exec ollama ollama list
```

### Web Service Health

```bash
curl -I https://your-domain.com
```

## Troubleshooting

### Turbo Streams Not Working

Ensure Traefik isn't buffering WebSocket connections. The compose file includes buffering middleware, but verify in Traefik logs.
Check that WebSocket upgrade headers are being passed correctly.

### Celery Tasks Not Processing

Check Redis connection:

```bash
docker-compose exec worker celery -A celery_app.celery inspect active
```

### Ollama Connection Failed

Verify `OLLAMA_HOST` is set and ollama is healthy:

```bash
docker compose exec web env | grep OLLAMA
docker compose exec ollama ollama list
```

### Permission Errors

Ensure mounted directories are writable:

```bash
chmod -R 755 data uploads
```

### Out of Disk Space (Ollama Models)

Models are large (~5GB each). Check:

```bash
df -h
docker system df
```

Prune unused Docker data:

```bash
docker system prune -a --volumes
```

## Security Considerations

1. **Change SECRET_KEY**: Use a strong random key in production
2. **Database Backups**: Automate regular backups of `data/receipe.db`
3. **Traefik TLS**: Ensure Let's Encrypt certificates auto-renew
4. **Firewall**: Only expose ports 80/443 via Traefik
5. **Updates**: Regularly update base images and dependencies

## Performance Tuning

### Gunicorn Workers

Edit `web.command` in `docker-compose.yml`:

```yaml
command: >
  sh -c "
  flask db upgrade &&
  gunicorn --worker-class gevent --workers 4 --bind 0.0.0.0:8000 --timeout 120 --log-level info 'app:create_app()'
  "
```

Rule of thumb: `(2 × CPU cores) + 1`

### Celery Concurrency

Edit `worker.command`:

```yaml
command: celery -A celery_app.celery worker --loglevel=info --concurrency=4
```

### Redis Memory Limit

Add to `redis` service:

```yaml
command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

## Stopping Services

```bash
# Stop but keep containers
docker compose stop

# Stop and remove containers (keeps volumes)
docker compose down

# Remove everything including volumes (destructive!)
docker compose down -v
```

## Complete Reinstall

```bash
docker compose down redis-data
mkdir -p data uploads redis-data
mkdir -p data uploads
docker compose build --no-cache
docker compose up -d
```
