# Deployment Guide: Split-Host with Remote Traefik

This guide covers deploying the Recreation.gov Campsite Notifier when Traefik is running on a separate Docker host.

## Architecture Overview

```
┌─────────────────────────────────────┐
│   Traefik Host (traefik.host)      │
│                                     │
│   - Traefik Proxy                  │
│   - SSL/TLS Management             │
│   - Routes to app host             │
└─────────────────────────────────────┘
              │
              │ Routes traffic to
              ▼
┌─────────────────────────────────────┐
│   App Host (app.host)               │
│                                     │
│   - Recreation Backend :8000        │
│   - Recreation Frontend :3000       │
│   - MongoDB (internal)              │
└─────────────────────────────────────┘
```

## Prerequisites

### Traefik Host (Already Configured)
- Traefik running with Docker provider enabled
- Access to Docker socket (`/var/run/docker.sock`)
- HTTP provider configured for external services (file-based)
- SSL certificate resolver configured

### Application Host
- Docker and Docker Compose installed
- Network connectivity to Traefik host
- Firewall rules allowing Traefik host to access ports 8000 and 3000

## Method 1: Docker Labels via HTTP Provider (Recommended)

This method uses Traefik's file-based HTTP provider to route to services on remote hosts.

### Step 1: Configure Traefik Host

On the **Traefik host**, add a dynamic configuration file. If using file provider, create or update:

**`/path/to/traefik/dynamic/recreation-app.yml`:**
```yaml
http:
  routers:
    recreation-api:
      rule: "Host(`basecamp.highz.net`) && PathPrefix(`/api`)"
      service: recreation-api
      entryPoints:
        - http
      middlewares:
        - recreation-api-https-redirect

    recreation-api-secure:
      rule: "Host(`basecamp.highz.net`) && PathPrefix(`/api`)"
      service: recreation-api
      entryPoints:
        - https
      tls:
        certResolver: cloudflare  # Use your cert resolver name

    recreation-app:
      rule: "Host(`basecamp.highz.net`)"
      service: recreation-app
      entryPoints:
        - http
      middlewares:
        - recreation-app-https-redirect

    recreation-app-secure:
      rule: "Host(`basecamp.highz.net`)"
      service: recreation-app
      entryPoints:
        - https
      tls:
        certResolver: cloudflare  # Use your cert resolver name

  services:
    recreation-api:
      loadBalancer:
        servers:
          - url: "http://APP_HOST_IP:8000"  # Replace APP_HOST_IP with actual IP

    recreation-app:
      loadBalancer:
        servers:
          - url: "http://APP_HOST_IP:3000"  # Replace APP_HOST_IP with actual IP

  middlewares:
    recreation-api-https-redirect:
      redirectScheme:
        scheme: https
        permanent: false

    recreation-app-https-redirect:
      redirectScheme:
        scheme: https
        permanent: true
```

**Update Traefik's main configuration** to watch this directory:

**`traefik.yml` (on Traefik host):**
```yaml
providers:
  file:
    directory: /path/to/dynamic/
    watch: true
```

### Step 2: Deploy Application

On the **application host**:

```bash
# Navigate to project directory
cd /path/to/recreation-gov-notifier

# Create/update .env file
cp .env.example .env
nano .env  # Configure all required variables

# Deploy the application
docker-compose -f docker-compose.remote-traefik.yml up -d --build

# Verify services are running
docker-compose -f docker-compose.remote-traefik.yml ps

# Check logs
docker-compose -f docker-compose.remote-traefik.yml logs -f
```

### Step 3: Verify Connectivity

From the **Traefik host**, verify you can reach the application:

```bash
# Test backend
curl http://APP_HOST_IP:8000/api/health

# Test frontend
curl http://APP_HOST_IP:3000
```

### Step 4: Test via Domain

```bash
# Should redirect to HTTPS
curl -I http://basecamp.highz.net

# Should return 200 with SSL
curl -I https://basecamp.highz.net

# Test API
curl https://basecamp.highz.net/api/health
```

## Method 2: Docker Swarm Overlay Network

If both hosts are part of a Docker Swarm, you can use overlay networks for service discovery.

### Step 1: Initialize Swarm

On the **Traefik host**:
```bash
docker swarm init --advertise-addr TRAEFIK_HOST_IP
```

This outputs a join command like:
```
docker swarm join --token SWMTKN-1-xxx... TRAEFIK_HOST_IP:2377
```

### Step 2: Join App Host to Swarm

On the **application host**, run the join command:
```bash
docker swarm join --token SWMTKN-1-xxx... TRAEFIK_HOST_IP:2377
```

### Step 3: Create Overlay Network

On the **Traefik host**:
```bash
docker network create --driver overlay --attachable traefik-public
```

### Step 4: Update Traefik Configuration

On the **Traefik host**, ensure Traefik is connected to the overlay network:

```yaml
# In Traefik's docker-compose.yml or stack file
networks:
  traefik-public:
    external: true
```

### Step 5: Deploy Application as Stack

On the **application host**, use a modified compose file:

**`docker-compose.swarm.yml`:**
```yaml
version: '3.8'

services:
  mongo:
    image: mongo:7.0
    networks:
      - recreation-network
    volumes:
      - mongo-data:/data/db
    deploy:
      placement:
        constraints:
          - node.hostname == app-host  # Pin to this host

  backend:
    image: recreation-backend:latest
    build:
      context: ./backend
    networks:
      - recreation-network
      - traefik-public
    environment:
      - MONGODB_URI=mongodb://mongo:27017
    env_file:
      - .env
    deploy:
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.recreation-api-secure.rule=Host(`basecamp.highz.net`) && PathPrefix(`/api`)"
        - "traefik.http.routers.recreation-api-secure.entrypoints=https"
        - "traefik.http.routers.recreation-api-secure.tls.certresolver=cloudflare"
        - "traefik.http.services.recreation-api.loadbalancer.server.port=8000"
        - "traefik.docker.network=traefik-public"

  frontend:
    image: recreation-frontend:latest
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
      args:
        - REACT_APP_API_URL=https://basecamp.highz.net
    networks:
      - traefik-public
    deploy:
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.recreation-app-secure.rule=Host(`basecamp.highz.net`)"
        - "traefik.http.routers.recreation-app-secure.entrypoints=https"
        - "traefik.http.routers.recreation-app-secure.tls.certresolver=cloudflare"
        - "traefik.http.services.recreation-app.loadbalancer.server.port=80"
        - "traefik.docker.network=traefik-public"

volumes:
  mongo-data:

networks:
  recreation-network:
    driver: overlay
  traefik-public:
    external: true
```

Deploy as a stack:
```bash
docker stack deploy -c docker-compose.swarm.yml recreation
```

## Firewall Configuration

### Application Host

Allow incoming traffic from Traefik host:

```bash
# UFW (Ubuntu)
sudo ufw allow from TRAEFIK_HOST_IP to any port 8000 proto tcp
sudo ufw allow from TRAEFIK_HOST_IP to any port 3000 proto tcp

# iptables
sudo iptables -A INPUT -p tcp -s TRAEFIK_HOST_IP --dport 8000 -j ACCEPT
sudo iptables -A INPUT -p tcp -s TRAEFIK_HOST_IP --dport 3000 -j ACCEPT
```

### Traefik Host

Ensure outbound traffic is allowed (usually default).

## Environment Variables

Update `.env` on the **application host**:

```bash
# JWT Configuration
JWT_SECRET=your-super-secret-jwt-key-change-this

# MongoDB
MONGODB_URI=mongodb://mongo:27017

# Email Configuration (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Twilio (optional, for SMS)
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+1234567890

# VAPID keys for push notifications
VAPID_PRIVATE_KEY=your-vapid-private-key
VAPID_PUBLIC_KEY=your-vapid-public-key
VAPID_CLAIMS={"sub":"mailto:your-email@example.com"}
```

## Monitoring and Logs

### Application Host

```bash
# View all logs
docker-compose -f docker-compose.remote-traefik.yml logs -f

# View specific service
docker-compose -f docker-compose.remote-traefik.yml logs -f backend

# Check service status
docker-compose -f docker-compose.remote-traefik.yml ps
```

### Traefik Host

Check Traefik dashboard or logs to verify routing:
```bash
docker logs traefik --tail 100 -f
```

## Troubleshooting

### Services Not Accessible

1. **Verify ports are open:**
   ```bash
   # On app host
   netstat -tlnp | grep -E ':(8000|3000)'
   ```

2. **Test connectivity from Traefik host:**
   ```bash
   # On Traefik host
   telnet APP_HOST_IP 8000
   curl http://APP_HOST_IP:8000/api/health
   ```

3. **Check firewall rules:**
   ```bash
   # On app host
   sudo ufw status
   sudo iptables -L -n | grep -E '(8000|3000)'
   ```

### SSL Certificate Issues

1. **Verify Traefik can request certificates:**
   - Check DNS is pointing to Traefik host, not app host
   - Verify certificate resolver is configured correctly
   - Check Traefik logs for certificate errors

2. **Check Traefik dynamic config:**
   ```bash
   # On Traefik host
   cat /path/to/dynamic/recreation-app.yml
   ```

### API Requests Failing

1. **CORS configuration:**
   - Ensure `backend/main.py` allows the domain
   - Check for `Access-Control-Allow-Origin` headers

2. **Backend health check:**
   ```bash
   # Direct check on app host
   curl http://localhost:8000/api/health
   
   # Via Traefik
   curl https://basecamp.highz.net/api/health
   ```

### Swarm-Specific Issues

1. **Service not discovering:**
   ```bash
   docker service ls
   docker service ps recreation_backend
   ```

2. **Network connectivity:**
   ```bash
   # Check overlay network
   docker network inspect traefik-public
   ```

3. **Node availability:**
   ```bash
   docker node ls
   ```

## Updates and Maintenance

### Update Application (Method 1: File Provider)

```bash
# On app host
cd /path/to/recreation-gov-notifier
git pull origin main
docker-compose -f docker-compose.remote-traefik.yml up -d --build
```

### Update Application (Method 2: Swarm)

```bash
# On app host
docker build -t recreation-backend:latest ./backend
docker build -t recreation-frontend:latest ./frontend
docker stack deploy -c docker-compose.swarm.yml recreation
```

### Backup MongoDB

```bash
# On app host
docker exec recreation-mongo mongodump --out=/dump
docker cp recreation-mongo:/dump ./mongo-backup-$(date +%Y%m%d)
```

## Security Best Practices

1. **Restrict firewall rules** to only Traefik host IP
2. **Use internal networks** - don't expose MongoDB externally
3. **Keep services updated** - regular `docker pull` for base images
4. **Monitor logs** for suspicious activity
5. **Use strong JWT secret** in production
6. **Enable rate limiting** in Traefik if not already configured
7. **Consider VPN/VPC** for cross-host communication instead of public IPs

## Production Checklist

- [ ] DNS A record points to Traefik host
- [ ] SSL certificate configured and working
- [ ] Firewall rules allow Traefik → App host (ports 8000, 3000)
- [ ] .env file configured with production credentials
- [ ] JWT secret is strong and unique
- [ ] SMTP credentials configured for email notifications
- [ ] VAPID keys generated for push notifications
- [ ] MongoDB data volume configured for persistence
- [ ] Backup strategy in place
- [ ] Monitoring/alerting configured
- [ ] Logs aggregation set up
- [ ] CORS properly restricted in backend
- [ ] Rate limiting configured (via Traefik or backend)

## Next Steps

- Configure automated backups
- Set up log aggregation (Loki, ELK)
- Configure monitoring (Prometheus/Grafana)
- Set up health check monitoring
- Configure email alerts for failures
- Document rollback procedures
