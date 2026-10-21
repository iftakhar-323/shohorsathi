# Deploying ShohorSathi

One Linux server (4 vCPU / 8 GB RAM is enough to start) with Docker. Use a server in Bangladesh (see
`docs/compliance.md`). Three domains point to it, e.g. `shohorsathi.com`, `partner.shohorsathi.com`,
`admin.shohorsathi.com`.

## First deploy

```bash
git clone https://github.com/iftakhar-323/shohorsathi && cd shohorsathi
./scripts/gen-jwt-keys.sh
cp .env.example .env.prod
```

Edit `.env.prod`:

- `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS=<the three domains>`, `CSRF_TRUSTED_ORIGINS=https://<each domain>`
- a long random value for every `*_SECRET_KEY`, `POSTGRES_PASSWORD` and `INTERNAL_API_TOKEN`
- `MEDIA_ENCRYPTION_KEY` — `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
  **Back this key up separately; without it the NID files cannot be read.**
- `CUSTOMER_DOMAIN`, `PARTNER_DOMAIN`, `ADMIN_DOMAIN`, `CORS_ALLOWED_ORIGINS`
- `PUBLIC_API_URL=https://<customer domain>`, `CUSTOMER_WEB_URL=https://<customer domain>`
- `PAYMENT_GATEWAY=sslcommerz` with the store id/password and `SSLCOMMERZ_SANDBOX=0`
- `SMS_BACKEND=http` with the SMS gateway URL/key, and `SENTRY_DSN`

Issue the first certificates (port 80 must be free), then start everything:

```bash
for d in $CUSTOMER_DOMAIN $PARTNER_DOMAIN $ADMIN_DOMAIN; do
  docker run --rm -p 80:80 -v $PWD/deploy/letsencrypt:/etc/letsencrypt certbot/certbot:v2.11.0 \
    certonly --standalone -d $d --agree-tos -m ops@<your domain> -n
done
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose exec auth python manage.py createsuperuser
```

The `certbot` service renews certificates; after a renewal, `docker compose exec gateway nginx -s reload`.

## Backups

```bash
crontab -e   # 30 2 * * * cd /srv/shohorsathi && ./scripts/backup.sh >> backups/backup.log 2>&1
```

`backup.sh` dumps every service database and the uploaded files and keeps 14 days. Copy `backups/` off the server
every night (another site, still within Bangladesh). Practise `scripts/restore.sh backups/<stamp>` on a staging
copy once a month.

## Monitoring

- Health: `https://<domain>/api/<service>/health/` for each service (checks the database). Point an uptime monitor
  at these.
- Errors: Sentry (`SENTRY_DSN`) receives exceptions from web processes and Celery workers.
- Events: rows in each service's `shohor_common_outboxevent` table with `sent_at` empty for more than a minute mean
  the broker is unreachable; the relay retries every 10 seconds.

## Updating

```bash
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Migrations run when each service starts. Take a backup first when the release notes mention migrations.

## Incident: suspected data breach

1. Contain: rotate `INTERNAL_API_TOKEN`, secret keys and database passwords; revoke sessions by rotating the JWT key
   pair (`scripts/gen-jwt-keys.sh` into a new folder, swap, restart).
2. Find out what was exposed using `MediaAccess` logs, Sentry and nginx logs.
3. Report to the data protection authority and inform affected users as the Personal Data Protection Ordinance
   requires (see `docs/compliance.md`).
