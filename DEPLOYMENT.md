# DPLUS Dashboard - Deployment Guide

Complete guide for deploying the DPLUS Skin Analytics Dashboard using Docker on your VPS, Oracle Cloud, home server, or any cloud platform.

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Deployment Options](#deployment-options)
  - [Option 1: Docker Compose (Recommended)](#option-1-docker-compose-recommended)
  - [Option 2: Standalone Docker](#option-2-standalone-docker)
  - [Option 3: Local Development](#option-3-local-development)
- [Platform-Specific Guides](#platform-specific-guides)
  - [Oracle Cloud Free Tier](#oracle-cloud-free-tier)
  - [AWS EC2](#aws-ec2)
  - [DigitalOcean / Linode / Vultr](#digitalorge--linode--vultr)
  - [Home Server / NAS](#home-server--nas)
- [Security Best Practices](#security-best-practices)
- [SSL/HTTPS Setup](#sslhttps-setup)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# Clone and setup
git clone <your-repo-url>
cd DPLUS-Dashboard

# Copy environment file
cp .env.example .env

# Build and run
docker-compose up -d
```

Access your dashboard at: `http://your-server-ip:8501`

Default password: `dplus2024`

---

## Prerequisites

- **Docker** 20.10+ and **Docker Compose** 2.0+ (or **Docker Desktop**)
- **Server with**:
  - Minimum 1GB RAM (2GB recommended)
  - 10GB disk space
  - Linux (Ubuntu 20.04+/22.04 recommended) or any Docker-compatible OS

### Installing Docker & Docker Compose

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose (if not included)
sudo apt-get update && sudo apt-get install docker-compose-plugin
```

**CentOS/RHEL:**
```bash
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io
sudo systemctl start docker
sudo systemctl enable docker
```

---

## Deployment Options

### Option 1: Docker Compose (Recommended)

**Best for:** VPS, cloud servers, home servers

```bash
# 1. Clone repository
git clone <your-repo-url> && cd DPLUS-Dashboard

# 2. Configure environment
cp .env.example .env
nano .env  # Edit if needed

# 3. Start the service
docker compose up -d

# 4. View logs
docker compose logs -f

# 5. Stop the service
docker compose down
```

**Environment Variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_PORT` | `8501` | Port to expose the dashboard |
| `APP_PASSWORD` | `dplus2024` | Dashboard login password |

---

### Option 2: Standalone Docker

**Best for:** Simple deployments without compose

```bash
# Build image
docker build -t dplus-dashboard .

# Run container
docker run -d \
  --name dplus-dashboard \
  --restart unless-stopped \
  -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  dplus-dashboard

# View logs
docker logs -f dplus-dashboard

# Stop container
docker stop dplus-dashboard
```

---

### Option 3: Local Development

**Best for:** Development, testing

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run dashboard
streamlit run src/app.py
```

---

## Platform-Specific Guides

### Oracle Cloud Free Tier

Oracle Cloud offers a generous free tier (4 ARM cores, 24GB RAM) - perfect for this dashboard.

1. **Create Instance:**
   - Go to Oracle Cloud Console → Compute → Instances
   - Create Instance: Always Free shape (VM.Standard.E2.1.Micro)
   - Use Ubuntu 22.04 Minimal

2. **Setup Firewall:**
   ```bash
   # In Oracle Cloud Console, add Ingress Rule:
   # Source: 0.0.0.0/0  Destination Port: 8501  Protocol: TCP
   ```

3. **Deploy:**
   ```bash
   ssh ubuntu@your-oracle-ip
   sudo apt-get update && sudo apt-get install -y git docker.io docker-compose
   git clone <your-repo-url>
   cd DPLUS-Dashboard
   docker compose up -d
   ```

---

### AWS EC2

1. **Launch EC2:**
   - Instance type: `t3.micro` or `t3.small` (Free Tier eligible)
   - AMI: Ubuntu Server 22.04 LTS

2. **Configure Security Group:**
   - Add inbound rule: TCP Port 8501 from your IP (or 0.0.0.0/0)

3. **Deploy:**
   ```bash
   ssh -i your-key.pem ubuntu@your-ec2-ip
   # Follow Docker Compose steps above
   ```

---

### DigitalOcean / Linode / Vultr

1. **Create Droplet/VPS:**
   - $6-12/month tier (1-2GB RAM is sufficient)
   - OS: Ubuntu 22.04 LTS

2. **Deploy:**
   ```bash
   ssh root@your-vps-ip
   apt-get update && apt-get install -y git docker.io docker-compose
   git clone <your-repo-url>
   cd DPLUS-Dashboard
   docker compose up -d
   ```

---

### Home Server / NAS

**Synology:**
- Install Docker from Package Center
- Use Docker Compose via SSH or Task Scheduler

**TrueNAS:**
- Install Docker plugin
- Deploy using docker-compose

**Generic Linux Server:**
- Follow Docker Compose steps above
- Consider using Portainer for GUI management

---

## Security Best Practices

### 1. Change Default Password

**Method A: Via Environment Variable (Recommended)**
```bash
# Generate SHA1 hash of your password
echo -n "your_new_password" | sha1sum

# Add to .env file
echo "APP_PASSWORD=your_new_password" >> .env
```

**Method B: Hardcode in app.py (Not Recommended for Production)**
Edit [`src/app.py`](src/app.py:19) and update `APP_PASSWORD_HASH`

### 2. Use Reverse Proxy with SSL

Don't expose Streamlit directly to the internet. Use Nginx as a reverse proxy.

**Example Nginx Config:**
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Don't expose 8501 directly (use Nginx)
```

### 4. Keep Dependencies Updated

```bash
# Regularly update the image
docker compose pull
docker compose up -d --build
```

---

## SSL/HTTPS Setup

### Option 1: Certbot (Let's Encrypt) - Free SSL

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is configured automatically
```

### Option 2: Cloudflare Tunnel (Easiest)

1. Sign up for Cloudflare (free tier)
2. Add your domain
3. Install `cloudflared`:
   ```bash
   wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
   sudo dpkg -i cloudflared-linux-amd64.deb
   ```
4. Create tunnel:
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create dplus-dashboard
   cloudflared tunnel route dns dplus-dashboard yourdomain.com
   ```
5. Run tunnel:
   ```bash
   cloudflared tunnel run dplus-dashboard
   ```

---

## Monitoring & Maintenance

### View Logs

```bash
# Real-time logs
docker compose logs -f

# Last 100 lines
docker compose logs --tail 100

# Specific service
docker compose logs -f dashboard
```

### Backup Data

```bash
# Backup DuckDB database
docker exec dplus-dashboard tar czf - /app/data | gzip > backup-$(date +%Y%m%d).tar.gz
```

### Health Check

```bash
# Check if container is running
docker ps

# Test health endpoint
curl http://localhost:8501/_stcore/health
```

### Restart Services

```bash
# Graceful restart
docker compose restart

# Force rebuild and restart
docker compose up -d --build --force-recreate
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs

# Common issues:
# - Port 8501 already in use → Change DASHBOARD_PORT in .env
# - Permission issues → Check data directory permissions
```

### Out of memory

```bash
# Add memory limit to docker-compose.yml:
services:
  dashboard:
    deploy:
      resources:
        limits:
          memory: 1G
```

### Database errors

```bash
# Clear database and restart
rm -rf data/*.db data/*.duckdb
docker compose restart
```

### Can't access from external IP

```bash
# Check firewall
sudo ufw status

# Check if listening on all interfaces
docker exec dplus-dashboard netstat -tlnp | grep 8501
# Should show 0.0.0.0:8501, not 127.0.0.1:8501
```

---

## Performance Optimization

For large datasets (10GB+ files):

1. **Use DuckDB's native query capability** - already implemented
2. **Increase container memory:**
   ```yaml
   # In docker-compose.yml
   services:
     dashboard:
       mem_limit: 4g
   ```
3. **Use fast storage** - NVMe SSD recommended for data files

---

## Support

For issues or questions:
- Check logs: `docker compose logs -f`
- Review this deployment guide
- Open an issue on GitHub
