# Quick Start Commands

## Development
```bash
docker-compose up -d
```

## Production Deployment
```bash
# First time setup
docker network create traefik-public
touch traefik/acme.json
chmod 600 traefik/acme.json

# Deploy
docker-compose -f docker-compose.prod.yml up -d --build

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment guide.
