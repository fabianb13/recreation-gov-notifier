# Deployment Guide: basecamp.highz.net with Traefik (All-in-One)

This guide covers deploying the Recreation.gov Campsite Notifier to a production server using Traefik as a reverse proxy with automatic HTTPS via Let's Encrypt.

**For split-host deployments** (Traefik on separate machine), see [DEPLOYMENT-REMOTE-TRAEFIK.md](DEPLOYMENT-REMOTE-TRAEFIK.md).

## Prerequisites

### 1. Domain Setup
- DNS A record pointing `basecamp.highz.net` to your server's IP address
- Optional: DNS A record for `traefik.highz.net` (Traefik dashboard)

### 2. Server Requirements
- Linux server (Ubuntu 20.04+ recommended)
- Docker and Docker Compose installed
- Ports 80 and 443 open in firewall

### 3. Cloudflare (Optional but Recommended)
If using Cloudflare DNS challenge for Let's Encrypt:
- Cloudflare account with your domain
- API token with `Zone:Read, DNS:Edit` permissions
- Or Global API Key (less secure)

## Initial Setup

### Step 1: Create Traefik Network
```bash
docker network create traefik-public
```

### Step 2: Configure Traefik SSL Certificate Storage
```bash
cd /path/to/recreation-gov-notifier
mkdir -p traefik
touch traefik/acme.json
chmod 600 traefik/acme.json
```

### Step 3: Update Environment Variables
Edit `.env` file:

```bash
# Update existing variables
JWT_SECRET=<generate-strong-random-secret>
MONGODB_URI=mongodb://mongo:27017

# Add Cloudflare credentials (if using DNS challenge)
CF_API_EMAIL=your-email@example.com
CF_API_KEY=your-cloudflare-api-key

# Email configuration (required for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Twilio (if using SMS)
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+1234567890

# VAPID keys for push notifications
VAPID_PRIVATE_KEY=<from-backend/generate_vapid_keys.py>
VAPID_PUBLIC_KEY=<from-backend/generate_vapid_keys.py>
VAPID_CLAIMS={"sub":"mailto:your-email@example.com"}
```

### Step 4: Update Traefik Configuration
Edit `traefik/traefik.yml`:
- Replace `your-email@example.com` with your actual email for Let's Encrypt

**If NOT using Cloudflare DNS challenge**, replace the `certificatesResolvers` section:
```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: your-email@example.com
      storage: acme.json
      httpChallenge:
        entryPoint: http
```

Then update `docker-compose.prod.yml` to use `letsencrypt` instead of `cloudflare` in all `tls.certresolver` labels.

### Step 5: Update Frontend API URL
The frontend needs to know where the API is. This is handled via build arg in `docker-compose.prod.yml`:
```yaml
args:
  - REACT_APP_API_URL=https://basecamp.highz.net
```

Update `frontend/src/api.js` to use the build-time environment variable:

```javascript
const getApiUrl = () => {
  // Use build-time env var in production, dynamic URL in development
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  // Fallback to dynamic URL for local development
  const protocol = window.location.protocol;
  const hostname = window.location.hostname;
  return `${protocol}//${hostname}:8000`;
};
```

### Step 6: Update CORS Settings
Edit `backend/main.py` to restrict CORS in production:

```python
# Production CORS - replace wildcard with specific domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://basecamp.highz.net"],  # Specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Or keep wildcard but add security headers via Traefik (already configured in `traefik/config.yml`).

## Deployment

### Deploy to Production Server

```bash
# Pull latest code
git pull origin main

# Build and start services
docker-compose -f docker-compose.prod.yml up -d --build

# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Verify services are running
docker-compose -f docker-compose.prod.yml ps
```

### Verify Deployment

1. **Check Traefik Dashboard** (if enabled): `https://traefik.highz.net`
   - Login with credentials (generate with `htpasswd` or online tool)
   
2. **Test Frontend**: `https://basecamp.highz.net`
   - Should redirect HTTP → HTTPS
   - Check browser console for errors
   
3. **Test API**: `https://basecamp.highz.net/api/health` or similar endpoint

4. **Check SSL Certificate**: 
   ```bash
   docker exec traefik cat /acme.json
   ```
   Should show certificate data (may take 1-2 minutes to generate)

5. **Test Push Notifications**:
   - HTTPS is required for service workers
   - Should now work on all devices/browsers

## Monitoring

### View Logs
```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f traefik
```

### Check Certificate Renewal
Let's Encrypt certificates auto-renew 30 days before expiry. Check logs:
```bash
docker-compose -f docker-compose.prod.yml logs traefik | grep -i certificate
```

## Troubleshooting

### SSL Certificate Not Generating
1. **Check DNS propagation**: `nslookup basecamp.highz.net`
2. **Verify ports open**: `sudo ufw status` (80 and 443)
3. **Check Traefik logs**: `docker logs traefik --tail 100`
4. **Cloudflare DNS challenge issues**:
   - Verify API credentials in `.env`
   - Check `CF_API_EMAIL` and `CF_API_KEY` are correct
   - Try `disablePropagationCheck: true` in `traefik.yml`

### API Requests Failing
1. **Check CORS settings** in `backend/main.py`
2. **Verify backend container running**: `docker ps | grep backend`
3. **Check backend logs**: `docker logs recreation-backend --tail 50`
4. **Test API directly**: `curl https://basecamp.highz.net/api/health`

### Frontend Not Loading
1. **Check nginx logs**: `docker logs recreation-frontend`
2. **Verify build completed**: Look for build output in logs
3. **Check browser console** for JavaScript errors
4. **Verify REACT_APP_API_URL** was set during build

### Push Notifications Not Working
1. **Verify HTTPS** (required for service workers)
2. **Check VAPID keys** in `.env`
3. **Verify service worker registered**: Browser DevTools → Application → Service Workers
4. **Check browser console** for errors

## Backup and Maintenance

### Backup MongoDB Data
```bash
docker exec recreation-mongo mongodump --out=/dump
docker cp recreation-mongo:/dump ./mongo-backup-$(date +%Y%m%d)
```

### Update Application
```bash
git pull origin main
docker-compose -f docker-compose.prod.yml up -d --build
```

### Restart Services
```bash
# Restart all
docker-compose -f docker-compose.prod.yml restart

# Restart specific service
docker-compose -f docker-compose.prod.yml restart backend
```

## Security Considerations

1. **Change default JWT secret** in `.env`
2. **Restrict CORS** to specific domain (not wildcard)
3. **Enable Traefik dashboard authentication** (already configured)
4. **Regular updates**: Keep Docker images updated
5. **Firewall**: Only expose ports 80 and 443
6. **Environment variables**: Never commit `.env` to git
7. **MongoDB**: Not exposed externally (only on internal network)

## Performance Optimization

1. **Enable MongoDB indexes** (already done in `backend/database.py`)
2. **Adjust scheduler interval** if needed (default: 300s)
3. **Monitor rate limiting**: Check for 429 errors in logs
4. **Nginx caching**: Already configured in `nginx.conf`
5. **Gzip compression**: Enabled in nginx config

## Alternative: HTTP Challenge Instead of DNS Challenge

If you don't want to use Cloudflare or DNS challenge, use HTTP challenge:

1. Update `traefik/traefik.yml`:
```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: your-email@example.com
      storage: acme.json
      httpChallenge:
        entryPoint: http
```

2. Update `docker-compose.prod.yml`: Replace all instances of `certresolver=cloudflare` with `certresolver=letsencrypt`

3. Remove Cloudflare environment variables from `.env` and docker-compose

## Next Steps

- Set up automated backups
- Configure monitoring (Prometheus/Grafana)
- Set up log aggregation (ELK stack, Loki)
- Configure email alerts for scheduler failures
- Set up health checks and uptime monitoring
