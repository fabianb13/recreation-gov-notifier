# Recreation.gov Notifier - Deployment Quick Reference

## Scenario 1: All-in-One (Traefik + App on Same Host)

**Use:** `docker-compose.prod.yml`

**Setup:**
```bash
docker network create traefik-public
touch traefik/acme.json && chmod 600 traefik/acme.json
docker-compose -f docker-compose.prod.yml up -d --build
```

**Guide:** [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Scenario 2: Split-Host (Remote Traefik)

**Use:** `docker-compose.remote-traefik.yml`

**Setup:**

### On Traefik Host:
Create `/path/to/traefik/dynamic/recreation-app.yml`:
```yaml
http:
  routers:
    recreation-api-secure:
      rule: "Host(`basecamp.highz.net`) && PathPrefix(`/api`)"
      service: recreation-api
      entryPoints: [https]
      tls:
        certResolver: cloudflare

    recreation-app-secure:
      rule: "Host(`basecamp.highz.net`)"
      service: recreation-app
      entryPoints: [https]
      tls:
        certResolver: cloudflare

  services:
    recreation-api:
      loadBalancer:
        servers:
          - url: "http://YOUR_APP_HOST_IP:8000"

    recreation-app:
      loadBalancer:
        servers:
          - url: "http://YOUR_APP_HOST_IP:3000"
```

### On App Host:
```bash
# Configure environment
cp .env.example .env
nano .env  # Update all variables

# Allow Traefik host through firewall
sudo ufw allow from TRAEFIK_HOST_IP to any port 8000
sudo ufw allow from TRAEFIK_HOST_IP to any port 3000

# Deploy
docker-compose -f docker-compose.remote-traefik.yml up -d --build
```

**Guide:** [DEPLOYMENT-REMOTE-TRAEFIK.md](DEPLOYMENT-REMOTE-TRAEFIK.md)

---

## Scenario 3: Development (Local)

**Use:** `docker-compose.yml`

**Setup:**
```bash
docker-compose up -d
```

Access:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- MongoDB: localhost:27017

---

## Common Commands

### View Logs
```bash
# All services
docker-compose -f <compose-file> logs -f

# Specific service
docker-compose -f <compose-file> logs -f backend
```

### Restart Services
```bash
# All services
docker-compose -f <compose-file> restart

# Specific service
docker-compose -f <compose-file> restart backend
```

### Update Application
```bash
git pull origin main
docker-compose -f <compose-file> up -d --build
```

### Backup MongoDB
```bash
docker exec recreation-mongo mongodump --out=/dump
docker cp recreation-mongo:/dump ./backup-$(date +%Y%m%d)
```

### Check Status
```bash
docker-compose -f <compose-file> ps
docker-compose -f <compose-file> top
```

---

## Environment Variables (.env)

Required variables:
```bash
# Security
JWT_SECRET=your-strong-random-secret

# Database
MONGODB_URI=mongodb://mongo:27017

# Email Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# SMS (optional)
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_FROM_NUMBER=+1234567890

# Push Notifications
VAPID_PRIVATE_KEY=xxx
VAPID_PUBLIC_KEY=xxx
VAPID_CLAIMS={"sub":"mailto:your-email@example.com"}
```

Generate VAPID keys:
```bash
cd backend
python generate_vapid_keys.py
```

---

## Troubleshooting

### Can't connect to services
```bash
# Check if running
docker ps

# Check logs
docker logs recreation-backend --tail 50

# Check network
docker network inspect recreation-network
```

### SSL certificate issues
- Verify DNS points to correct host (Traefik host for split setup)
- Check Traefik logs: `docker logs traefik --tail 100`
- Verify Let's Encrypt rate limits not exceeded

### Push notifications not working
- HTTPS required (check SSL certificate)
- Verify VAPID keys in .env
- Check browser console for errors
- Verify service worker registered

### API requests failing
- Check CORS settings in backend/main.py
- Verify backend is accessible: `curl http://localhost:8000/api/health`
- Check browser network tab for error details

---

## Quick Health Checks

```bash
# Backend health
curl http://localhost:8000/api/health  # Local
curl https://basecamp.highz.net/api/health  # Production

# Frontend accessible
curl -I http://localhost:3000  # Local
curl -I https://basecamp.highz.net  # Production

# MongoDB connection
docker exec recreation-mongo mongosh --eval "db.adminCommand('ping')"

# Check SSL
curl -I https://basecamp.highz.net  # Should return 200 with HTTPS
```
