# VPS Deployment Guide

This guide explains how to deploy the VoiceClone API to your VPS.

## Prerequisites

1. **VPS Requirements**:
   - Ubuntu 22.04+ (or similar Linux)
   - 8+ CPU cores
   - 32GB RAM
   - 50GB+ storage
   - Docker & Docker Compose installed

2. **Modal.com TTS Service**: Already deployed (see [MODAL_DEPLOYMENT.md](./MODAL_DEPLOYMENT.md))

3. **Domain (Optional)**: For HTTPS access

## Step 1: Prepare VPS

### Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

### Create Project Directory

```bash
sudo mkdir -p /opt/voiceclone
sudo chown $USER:$USER /opt/voiceclone
cd /opt/voiceclone
```

## Step 2: Clone Repository

```bash
# Clone your repository
git clone https://github.com/YOUR_USERNAME/voiceclone.git .

# Or copy files manually if not using git
```

## Step 3: Configure Environment

Create the `.env` file:

```bash
cat > .env << 'EOF'
# Application
APP_ENV=production
DEBUG=false
SECRET_KEY=your-super-secret-key-change-this

# Database
DB_PASSWORD=your-secure-database-password

# Modal.com TTS Service
MODAL_TTS_ENDPOINT=https://your-workspace--voiceclone-tts-synthesize.modal.run

# Optional: Modal credentials (for future use)
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=

# CORS (add your frontend domain)
CORS_ORIGINS=https://yourdomain.com,http://localhost:3000
EOF

# Secure the file
chmod 600 .env
```

### Generate a Secure Secret Key

```bash
# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Step 4: Deploy with Docker Compose

```bash
# Build and start services
docker compose up -d

# View logs
docker compose logs -f

# Check status
docker compose ps
```

### Expected Services

| Service | Port | Description |
|---------|------|-------------|
| api | 8000 | FastAPI application |
| db | 5432 | PostgreSQL database |
| redis | 6379 | Redis cache |
| nginx | 80/443 | Reverse proxy (optional) |

## Step 5: Run Database Migrations

```bash
# Run migrations
docker compose exec api alembic upgrade head
```

## Step 6: Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","app":"voiceclone","env":"production"}

# Test API docs (if enabled)
curl http://localhost:8000/docs
```

## Step 7: Configure Firewall

```bash
# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow SSH (don't lock yourself out!)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
sudo ufw status
```

## Step 8: Setup SSL (Production)

### Option A: Using Certbot (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot -y

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com

# Copy certificates
sudo mkdir -p /opt/voiceclone/nginx/ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/voiceclone/nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/voiceclone/nginx/ssl/
```

### Option B: Using Cloudflare

If using Cloudflare, set SSL mode to "Flexible" or "Full" in your Cloudflare dashboard.

### Enable HTTPS in Nginx

Edit `nginx/nginx.conf` and uncomment the HTTPS server block, then:

```bash
# Restart nginx
docker compose restart nginx
```

## GitHub Actions Deployment

### Required Secrets

Add these secrets to your GitHub repository (Settings → Secrets → Actions):

| Secret | Description | Example |
|--------|-------------|---------|
| `VPS_HOST` | VPS IP or hostname | `203.0.113.1` |
| `VPS_USERNAME` | SSH username | `deploy` |
| `VPS_SSH_KEY` | Private SSH key | (full key content) |
| `VPS_SSH_PORT` | SSH port (optional) | `22` |
| `SECRET_KEY` | App secret key | (generated value) |
| `DB_PASSWORD` | Database password | (secure password) |
| `MODAL_TTS_ENDPOINT` | Modal endpoint URL | `https://...modal.run` |

### Setup Deploy User (Recommended)

```bash
# Create deploy user
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG docker deploy

# Setup SSH key
sudo mkdir -p /home/deploy/.ssh
sudo nano /home/deploy/.ssh/authorized_keys
# Paste your public key

sudo chown -R deploy:deploy /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys

# Give deploy user access to project
sudo chown -R deploy:deploy /opt/voiceclone
```

## Monitoring

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api

# Last 100 lines
docker compose logs --tail=100 api
```

### Resource Usage

```bash
# Container stats
docker stats

# Disk usage
docker system df
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database health
docker compose exec db pg_isready -U voiceclone

# Redis health
docker compose exec redis redis-cli ping
```

## Backup & Recovery

### Backup Database

```bash
# Create backup
docker compose exec db pg_dump -U voiceclone voiceclone > backup_$(date +%Y%m%d).sql

# Backup voice files
tar -czvf voices_backup_$(date +%Y%m%d).tar.gz /var/lib/docker/volumes/voiceclone_voice_data/
```

### Restore Database

```bash
# Restore from backup
cat backup_20250102.sql | docker compose exec -T db psql -U voiceclone voiceclone
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs api

# Common issues:
# - Database not ready: Wait for db healthcheck
# - Port conflict: Check if port 8000 is in use
# - Memory issues: Check available RAM
```

### Database connection failed

```bash
# Check database is running
docker compose ps db

# Check database logs
docker compose logs db

# Verify connection
docker compose exec api python -c "from voiceclone.core.database import engine; print('OK')"
```

### Modal endpoint not reachable

```bash
# Test Modal endpoint directly
curl -X POST "YOUR_MODAL_ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{"model": "orpheus", "text": "test", "voice": "tara"}'
```

### Out of disk space

```bash
# Clean up Docker
docker system prune -a

# Remove old logs
sudo journalctl --vacuum-time=7d
```

## Updating

### Manual Update

```bash
cd /opt/voiceclone

# Pull latest code
git pull origin main

# Rebuild and restart
docker compose build
docker compose up -d

# Run migrations
docker compose exec api alembic upgrade head
```

### Via GitHub Actions

Just push to `main` branch - the workflow handles everything automatically.

## Performance Tuning

### Increase Worker Count

Edit `docker-compose.yml`:

```yaml
api:
  command: ["uvicorn", "voiceclone.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### PostgreSQL Tuning

For 32GB RAM, add to `docker-compose.yml`:

```yaml
db:
  command:
    - "postgres"
    - "-c"
    - "shared_buffers=8GB"
    - "-c"
    - "effective_cache_size=24GB"
    - "-c"
    - "work_mem=256MB"
```

## Security Checklist

- [ ] Change default passwords
- [ ] Enable firewall (UFW)
- [ ] Setup SSL/HTTPS
- [ ] Disable debug mode in production
- [ ] Use non-root user for deployment
- [ ] Regular security updates
- [ ] Enable fail2ban for SSH protection
- [ ] Backup regularly
