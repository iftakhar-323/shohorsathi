# ShohorSathi (শহরসাথী)

City-based problem solution marketplace — products, trusted services and city issue reporting in one platform.

**Stack (strict):** Django + Django REST Framework · React (Vite + TypeScript) · PostgreSQL

UI design canvas (customer home, booking, provider inbox, admin dashboard): https://claude.ai/artifact/C74ShN6dNDX2E6W4M9GD9v

## Architecture

Each backend domain is a separate Django service with its **own PostgreSQL database**. An Nginx gateway routes
`/api/*` to the right service. The auth service signs JWTs with an RS256 private key; every other service only
verifies them with the public key (no call back to auth).

```
apps/customer-web ─┐
apps/provider-web ─┼─► gateway (nginx :8088) ─► services/auth     ─► auth_db
apps/admin-web    ─┘                         ─► services/catalog  ─► catalog_db
                                             ─► ... (one service per phase)
```

| Path | What |
|---|---|
| `services/common` | Shared Python package (`shohor_common`): role permissions, JWT settings helper |
| `services/auth` | Users, roles, phone OTP, JWT, areas, saved addresses |
| `services/catalog` | Categories, products, services, fixed prices |
| `apps/customer-web` | Customer React app |
| `gateway` | Nginx routing config |
| `infra` | Postgres init scripts |

## Run locally

```bash
./scripts/gen-jwt-keys.sh          # creates .keys/jwt_private.pem + jwt_public.pem (gitignored)
cp .env.example .env
docker compose up --build          # postgres :5433, redis, auth, catalog, gateway :8088

# seed + admin user
docker compose exec auth python manage.py createsuperuser
docker compose exec catalog python manage.py seed_catalog

# frontend
pnpm install
pnpm --filter customer-web dev     # http://localhost:5173 (proxies /api to :8088)
```

API docs: `http://localhost:8088/api/auth/docs/`, `http://localhost:8088/api/catalog/docs/`

## Tests

```bash
docker compose exec auth pytest
docker compose exec catalog pytest
pnpm --filter customer-web build
```

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 — Foundation | Monorepo, Docker, gateway, auth + catalog services, customer home | done |
| 1 — MVP | Cart & orders (COD), service booking, provider portal, custom requests, admin panel | |
| 2 — Subscriptions & Trust | 7/15/30-day cleaning & meal plans, online payment, reviews, chat, notifications | |
| 3 — City Layer | Issue reporting, live map, emergency request, community hub | |
| 4 — Scale | Loyalty, B2B, analytics, multi-city | |
