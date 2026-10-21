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
                                              ├─► subscription    ─► subscription_db
                                              ├─► payment         ─► payment_db
                                              ├─► chat (ASGI/WS)  ─► chat_db
                                              ├─► notification    ─► notification_db
                                              ├─► city            ─► city_db
                                              ├─► loyalty         ─► loyalty_db
                                              ├─► b2b             ─► b2b_db
                                              └─► analytics       ─► analytics_db
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
| `services/subscription` | 7/15/30-day cleaning, meal and household plans: schedules, skip (10 PM cutoff), pause, cancel, renew, upgrade, same-cleaner pin, 48h re-clean, group meals, student discount, meal menu |
| `services/payment` | SSLCommerz (bKash/Nagad/cards) or a dev mock gateway; escrow ledger (held → released / refunded), refund & complaint requests |
| `services/chat` | Django Channels: customer ↔ provider job chats, customer ↔ support with FAQ auto-reply; REST + WebSocket |
| `services/city` | City issue reporting (photo + map pin, duplicate detection, upvotes, forward to authorities, resolve with photos) and the neighbourhood community hub |
| `services/loyalty` | Points (earned on completed orders and subscriptions, redeemed at checkout), in-app wallet (top-up, pay, refunds on cancel), referrals, badges |
| `services/b2b` | Building committees & businesses: members, annual maintenance contracts with scheduled visits, monthly invoices/receipts, corporate dashboard |
| `services/analytics` | Event facts → GMV, revenue, commission, top services, new vs returning customers, demand heatmap, per-city filter |
| `services/notification` | In-app notifications (Bangla + English) and SMS from events; admin broadcasts |
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
- **Subscription:** subscribe (quote with prepay/student/add-on/group pricing) → pay cash or online → visits/meals are
  scheduled → every night at the cutoff tomorrow's visits become provider jobs (`subscription.visit_due`), pinned to
  the home's regular provider after the first visit → ratings feed the provider's score; skipped/paused/bad meals
  become credit for the next renewal, which runs automatically.
- **Online payment:** the amount is always fetched from the owning service; the gateway's callback/IPN is validated
  and moves money into escrow; completion of the order/request releases it, cancellation refunds it automatically.
- **City issue:** report with photo and map pin (an open issue of the same kind within 50 m is offered for upvoting
  instead) → admin forwards it to the matching authority → in progress → resolved with photos; reporter and upvoters
  are notified at each step.
- **Emergency:** one tap → emergency-capable services for today with a priority charge → the nearest online providers
  are alerted first → live provider location on the customer's map while on the way.
- **Loyalty:** completed orders earn points (and pay out a pending referral); at checkout points give a capped
  discount and the wallet can pay; a cancelled order returns both. Wallet top-ups go through the payment gateway.
- **B2B:** an organization applies → admin approves → members order in its name; maintenance contracts schedule visits
  that are dispatched to providers nightly; on the 1st, each organization gets an invoice (contract fees + its
  completed orders) with a printable receipt.
- **Multi-city:** a city exists as soon as it has areas; customers pick their city, and analytics can be filtered by it.
- **Provider onboarding:** apply with NID/photos (kitchen photos for home chefs) → admin approves → `provider.approved`
  makes the user a provider (picked up on the next token refresh).

## Languages (Bangla + English)

All three apps are Bangla-first with an English switch (header / sidebar / login page; the choice is remembered per
browser). Write UI text in Bangla wrapped in `t()` from `@shohor/web-core` — the Bangla text is the key — and add the
English line to `packages/web-core/src/i18n/en.ts`. Placeholders: `t("{n} দিনের ওয়ারেন্টি", { n: 7 })`.
Catalog items and areas have `name_bn`/`name_en`; render them with `localName(item)`. Dates, numbers and Taka amounts
follow the selected language. CI runs `node packages/web-core/scripts/check-i18n.mjs`, which fails on a Bangla string
without an English translation or Bangla JSX text that is not wrapped in `t()`.

## Run locally

```bash
./scripts/gen-jwt-keys.sh          # creates .keys/jwt_private.pem + jwt_public.pem (gitignored)
cp .env.example .env
docker compose up --build          # postgres :5433, redis, all services + workers, gateway :8088

docker compose exec auth python manage.py createsuperuser     # admin login for admin-web
docker compose exec catalog python manage.py seed_catalog     # sample categories/services/products
docker compose exec subscription python manage.py seed_plans  # sample subscription plans/prices/add-ons

pnpm install
pnpm --filter customer-web dev     # http://localhost:5173
pnpm --filter provider-web dev     # http://localhost:5174
pnpm --filter admin-web dev        # http://localhost:5175
```

Payments use a local test checkout page (`PAYMENT_GATEWAY=mock`); set `PAYMENT_GATEWAY=sslcommerz` with store
credentials for real bKash/Nagad/card payments. SMS texts are logged (`SMS_BACKEND=console`) until an SMS gateway is set.
After editing `gateway/nginx.conf`, run `docker compose exec gateway nginx -s reload` (the folder is mounted, so the edit
is picked up).

In development OTP codes are written to the auth service log (`docker compose logs auth | grep OTP`).
Adding a database to an existing Postgres volume: run the new `CREATE DATABASE` line from `infra/postgres/init.sql`
with `docker compose exec postgres psql -U shohor`.

API docs per service: `http://localhost:8088/api/<service>/docs/` (auth, catalog, order, provider, custom_request, media).

## Tests

```bash
docker compose exec <service> pytest    # each Django service
python3 scripts/e2e_phase1.py           # Phase 1 flow through the gateway with real events (stack must be running)
python3 scripts/e2e_phase2.py           # subscriptions, payments/escrow, reviews, chat, notifications
python3 scripts/e2e_phase3.py           # city issues, community, emergency request, live tracking
python3 scripts/e2e_phase4.py           # wallet & points, referrals, B2B portal, analytics, multi-city
pnpm -r build                           # type-check and build all web apps
```

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 — Foundation | Monorepo, Docker, gateway, auth + catalog services, customer home | done |
| 1 — MVP | Cart & orders (COD), service booking, provider portal, custom requests, admin panel | done |
| 2 — Subscriptions & Trust | 7/15/30-day cleaning & meal plans, online payment + escrow, reviews, chat, notifications | done |
| 3 — City Layer | Issue reporting, live map, emergency request, community hub | done |
| 4 — Scale | Loyalty points & wallet, referrals, B2B portal, analytics, multi-city | done |
