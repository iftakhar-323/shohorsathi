# ShohorSathi (শহরসাথী)

City-based problem solution marketplace — products, trusted services and city issue reporting in one platform.

**Stack (strict):** Django + Django REST Framework · React (Vite + TypeScript) · PostgreSQL

UI design canvas (customer home, booking, provider inbox, admin dashboard): https://claude.ai/artifact/C74ShN6dNDX2E6W4M9GD9v

## Architecture

Each backend domain is a separate Django service with its **own PostgreSQL database**. An nginx gateway routes
`/api/*` to the right service. The auth service signs JWTs with an RS256 private key; every other service only
verifies them with the public key. Services talk to each other with **events** (Celery over Redis, see
`services/common/shohor_common/events.py`) and, for a few lookups, internal HTTP calls guarded by a shared token.

```
apps/customer-web ─┐                          ┌─► auth            ─► auth_db
apps/provider-web ─┼─► gateway (nginx :8088) ─┼─► catalog         ─► catalog_db
apps/admin-web    ─┘                          ├─► order           ─► order_db
                                              ├─► provider        ─► provider_db
                                              ├─► custom-request  ─► custom_request_db
                                              └─► media           ─► media_db (+ files volume)
            each service ◄──── events (Celery workers, Redis) ────► each service
```

| Path | What |
|---|---|
| `services/common` | Shared package `shohor_common`: settings, role permissions, event bus, internal calls, test helpers |
| `services/auth` | Users, roles, phone OTP, JWT, areas, saved addresses, user block/unblock |
| `services/catalog` | Categories, products, services, fixed prices, stock |
| `services/order` | Cart (products + services), COD checkout, bookings, tracking, arrival code, warranty claims |
| `services/provider` | Provider onboarding & verification, job inbox, smart matching, earnings, weekly payouts, trust score |
| `services/custom_request` | Custom service requests, admin quotes with cost breakdown, one counter-offer round |
| `services/media` | Photo/document uploads; NID files are always private |
| `packages/web-core` | Shared React code: API client with token refresh, auth, UI components, Bangla formatting |
| `apps/customer-web` | Customer site (:5173) |
| `apps/provider-web` | Provider portal (:5174) |
| `apps/admin-web` | Admin panel (:5175) |
| `scripts/new-service.sh` | Scaffolds a new Django service |

### Main flows

- **Booking:** cart → checkout → `booking.created` → provider job (open in matching area/skill, or admin assigns from
  smart suggestions) → provider accepts → on the way → enters customer's 4-digit arrival code → completes with photos →
  `job.status_changed` updates the booking/order → earning recorded (commission deducted) → weekly payout.
- **Custom request:** submit → admin reviews and quotes (labor/materials/transport/platform fee) → customer accepts,
  rejects or counters once → accepted request becomes a provider job; job progress flows back to the request.
- **Provider onboarding:** apply with NID/photos (kitchen photos for home chefs) → admin approves → `provider.approved`
  makes the user a provider (picked up on the next token refresh).

## Run locally

```bash
./scripts/gen-jwt-keys.sh          # creates .keys/jwt_private.pem + jwt_public.pem (gitignored)
cp .env.example .env
docker compose up --build          # postgres :5433, redis, all services + workers, gateway :8088

docker compose exec auth python manage.py createsuperuser     # admin login for admin-web
docker compose exec catalog python manage.py seed_catalog     # sample categories/services/products

pnpm install
pnpm --filter customer-web dev     # http://localhost:5173
pnpm --filter provider-web dev     # http://localhost:5174
pnpm --filter admin-web dev        # http://localhost:5175
```

In development OTP codes are written to the auth service log (`docker compose logs auth | grep OTP`).
Adding a database to an existing Postgres volume: run the new `CREATE DATABASE` line from `infra/postgres/init.sql`
with `docker compose exec postgres psql -U shohor`.

API docs per service: `http://localhost:8088/api/<service>/docs/` (auth, catalog, order, provider, custom_request, media).

## Tests

```bash
docker compose exec <service> pytest    # each Django service
python3 scripts/e2e_phase1.py           # full flow through the gateway with real events (stack must be running)
pnpm -r build                           # type-check and build all web apps
```

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 — Foundation | Monorepo, Docker, gateway, auth + catalog services, customer home | done |
| 1 — MVP | Cart & orders (COD), service booking, provider portal, custom requests, admin panel | done |
| 2 — Subscriptions & Trust | 7/15/30-day cleaning & meal plans, online payment, reviews, chat, notifications | |
| 3 — City Layer | Issue reporting, live map, emergency request, community hub | |
| 4 — Scale | Loyalty, B2B, analytics, multi-city | |
