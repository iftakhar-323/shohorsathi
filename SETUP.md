# Running ShohorSathi from a Fresh Clone

This guide takes you from `git clone` to all three web applications running with realistic demo data (Dhaka, Chattogram, and Khulna), and shows how to verify that everything works properly.

> **Quick Summary:**
> 
> - **Method 1: Zero-Docker Mode (Recommended for fast local testing & laptops without Docker):**
>   1. Start the backend: `python scripts/standalone_server.py` (answers on `:8088` with all seeded data in memory)
>   2. Start the frontend: `pnpm install` and `pnpm dev` (Customer `:5173`, Provider `:5174`, Admin `:5175`).
>   *(On Windows, you can simply double-click `run-windows.bat` to launch both automatically)*
> 
> - **Method 2: Full Docker Microservices Mode:**
>   Run `scripts/up.sh --demo` (or `scripts\up.bat --demo` on Windows). All demo accounts use password `demo1234`.

---

## ⚡ Option 1: Zero-Docker Quick Start (Windows, macOS, Linux)

If your laptop does not have Docker Desktop installed, or if you prefer a lightweight setup that starts in seconds without Docker/PostgreSQL/Redis:

```bash
git clone https://github.com/iftakhar-323/shohorsathi.git
cd shohorsathi

# 1. Start the zero-dependency backend server (Standard Python only, no pip installs needed):
python scripts/standalone_server.py

# 2. In a second terminal, start the web apps:
pnpm install
pnpm dev
```

*Windows Tip:* Simply double-click `run-windows.bat` in the project root to start both backend and frontend automatically in dedicated windows.

**How it works and what to expect:**

- Every page shows the real demo data: the API answers were recorded from the Docker backend into `demo/data/standalone_snapshot.json` and are replayed per user.
- The demo actions work and are kept in memory until the server stops:
  - cart and checkout (cash, bKash, Nagad or card through a mock payment page)
  - cancel and reschedule, reviews, saved addresses
  - city-problem reports with photos, upvotes, community posts
  - custom requests and quotes, subscriptions, home profile, AI quote
  - provider jobs (accept, arrival code, photos, complete)
  - admin quotes and issue forwarding
- Restarting the server resets everything to the clean demo state.
- It is a demo stand-in, not the backend. There is no live chat (websocket), no background jobs, and no real SMS. Sign-ups use OTP `123456`.
- After you change the seed data or the APIs, record a new snapshot. With the Docker stack running on fresh demo data and `pnpm dev` running, use `node scripts/standalone/record_snapshot.mjs`.

---

## 🐳 Option 2: Full Docker Microservices Architecture

### What runs where

```
 browser ──► customer-web :5173 ─┐
         ──► provider-web :5174 ─┼─ /api, /media ──► nginx gateway :8088 ──► 14 Django services (+ Celery workers)
         ──► admin-web    :5175 ─┘                                            │
                                                         PostgreSQL :5433 (one database per service) · Redis
```

The backend (gateway, services, Postgres, Redis) runs in Docker. The three React apps run on your machine with Vite and proxy `/api` and `/media` requests to the gateway.

### Prerequisites

| Tool | Version | Check with |
|---|---|---|
| Docker Engine (or Docker Desktop) with Compose v2 | Docker 24+, Compose 2.20+ | `docker compose version` |
| Node.js | 20 or newer | `node -v` |
| pnpm | 9 or newer (included via corepack) | `corepack enable && pnpm -v` |
| Python | 3.10 or newer | `python3 --version` |
| git, openssl, curl | Any recent version | |

- **Memory:** 8 GB RAM minimum, 16 GB recommended (31 containers). Disk: ~10 GB for images.
- **Ports required:** 5433 (Postgres), 8088 (gateway), 5173, 5174, 5175 (web applications).
- **Windows:** Use WSL 2 (Ubuntu) with Docker Desktop WSL integration enabled, or run via `scripts\up.bat --demo`.
- **Ubuntu/Debian installation:**
  ```bash
  sudo apt install -y git curl openssl python3
  curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
  sudo corepack enable
  ```

### Step 1: Clone Repository

```bash
git clone https://github.com/iftakhar-323/shohorsathi.git
cd shohorsathi
```

### Step 2: Build & Start Backend with Demo Data

```bash
scripts/up.sh --demo
# or on Windows Command Prompt:
scripts\up.bat --demo
```

This single command:
1. Creates `.env` from `.env.example`.
2. Generates JWT signing keys in `.keys/` (`scripts/gen-jwt-keys.sh`).
3. Builds the service images sequentially to prevent memory exhaustion on 8 GB machines.
4. Starts the containers with `docker compose up -d` and waits for gateway health checks.
5. Populates complete realistic demo data (`scripts/seed_demo.py`).

Expected output:
```
  ✓ Khulna: 14 orders across every service type (6 done and reviewed, 3 confirmed, 3 waiting for a provider, 2 product orders)
  ✓ Khulna: 5 authorities with feed links, 16 photo issues of all 8 kinds in 15 areas, 9 community posts
  ✓ analytics history: ... synthetic facts over 8 weeks
Demo data ready. Password for every account: demo1234
backend is up on http://localhost:8088
```

<details>
<summary>Manual Step-by-Step Alternative</summary>

```bash
cp .env.example .env
./scripts/gen-jwt-keys.sh
docker compose build auth            # repeat for each service, or `docker compose build` on 16GB+ RAM
docker compose up -d
docker compose ps                    # verify all containers are "Up"
python3 scripts/seed_demo.py         # once gateway responds on http://localhost:8088
```
</details>

---

## 🌐 Web Applications & Demo Accounts

In a second terminal, start the three React applications:

```bash
pnpm install          # First time only
pnpm dev              # Starts Customer, Provider, and Admin apps
```

| Application | URL | Demo Login (Password: `demo1234`) | Role & Notes |
|---|---|---|---|
| **Customer Web** | http://localhost:5173 | Dhaka: `01711000001` (Rahim - tenant)<br>`01711000002` (Nusrat) · `01711000003` (Tanvir)<br>Khulna: `01711000004` (Farhana) · `01711000005` (Arif) | Service booking, AI photo quote, Home Profile, city issue reporting, live order tracking |
| **Provider Portal** | http://localhost:5174 | Dhaka: `01811000001` (Karim - Electrician)<br>`01811000002` (Salma - Cleaner) · `01811000003` (Jamal - AC)<br>Khulna: `01811000006` (Saiful - AC/Plumbing) | Job inbox, accept jobs, instant payout, safety quiz certification, insurance claims |
| **Admin Panel** | http://localhost:5175 | `01700000000` (Super Admin) | Demand forecasting, churn prediction, fraud detection, city issues arbitration, catalog management |

Run an individual app only: `pnpm dev:customer`, `pnpm dev:provider`, or `pnpm dev:admin`.
Detailed demonstration walkthrough is documented in [DEMO.md](DEMO.md).

---

## 🧪 Verification & Automated Tests

**Quick Manual Check (2 minutes):**
- Open http://localhost:5173: verify home hero banner, sample categories, and language switcher.
- City switcher in the header allows selecting Dhaka, Chattogram, and Khulna.
- http://localhost:5173/ai-quote: click any demo problem image to test instant AI diagnostics and cost estimation.
- Log in to http://localhost:5175 as `01700000000`: check the Analytics dashboard and charts.

**Automated Test Suite:**

```bash
# Playwright End-to-End browser tour across all three apps (screenshots saved to apps/e2e/test-results/tour/)
pnpm --filter e2e exec playwright install --with-deps chromium     # first time only
pnpm --filter e2e exec playwright test tests/demo-tour.spec.ts

# Backend unit tests for any service
docker compose exec order pytest -q

# Integration E2E scenario scripts through API gateway
python3 scripts/e2e_phase1.py      # ... up to e2e_phase9.py

# Internationalization and build verification
pnpm build && pnpm check:i18n
```

---

## 🛠️ Essential Management Commands

| Action | Command |
|---|---|
| Stop all containers (retains data) | `docker compose stop` (press `Ctrl+C` in `pnpm dev` terminal) |
| Restart containers | `docker compose start` followed by `pnpm dev` |
| View running containers | `docker compose ps` |
| View logs for a service | `docker compose logs -f order` |
| View OTP code for a new sign-up (dev) | `docker compose logs auth \| grep "OTP for"` |
| Reset to fresh demo data (**clears all data**) | `docker compose down -v && scripts/up.sh --demo` |
| Create database & uploads backup | `scripts/backup.sh` (outputs to `backups/`) |
| Rebuild a specific service after code edits | `docker compose build <service> <service>-worker && docker compose up -d <service> <service>-worker` |

---

## ⚙️ Configuration Variables (`.env`)

- `ANTHROPIC_API_KEY`: Claude Vision API key for real-time visual inspection in AI Photo Quote. Without this key, an intelligent keyword and pattern matcher provides diagnostics automatically.
- `GATEWAY_PORT`: Defaults to `8088`. If taken, change to another port (e.g., `8090`) and run `GATEWAY_URL=http://localhost:8090 pnpm dev`.
- `PAYMENT_GATEWAY`: Defaults to `mock`. Set to `sslcommerz` with store credentials for production payments.

---

## 🔍 Troubleshooting

| Issue | Resolution |
|---|---|
| Windows CMD error: `set: pipefail: invalid option name` | CRLF line endings detected. Run `python -c "import pathlib; [p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n')) for p in pathlib.Path('scripts').glob('*.sh')]"` then re-run `bash scripts/up.sh --demo`, or use `python scripts/standalone_server.py`. |
| `permission denied ... docker.sock` | Run `sudo usermod -aG docker $USER`, then log out and log back in. |
| Build terminated with `exit code 137` / `Killed` | Insufficient host memory. Build images one by one (handled by `scripts/up.sh`) or increase memory allocation in Docker Desktop. |
| Port `5433` already allocated | Existing PostgreSQL instance detected. Stop conflicting service or change port mapping in `docker-compose.yml`. |
| Port `8088` already allocated | Set `GATEWAY_PORT=8090` in `.env`, run `docker compose up -d`, and run `GATEWAY_URL=http://localhost:8090 pnpm dev`. |
| Gateway returns `502 Bad Gateway` | Services are still completing initial migrations. Wait 20–30 seconds and check `docker compose ps`. |
| Missing photos or placeholder icons | Re-sync demo assets: run `python3 scripts/seed_demo.py` or `python3 scripts/download_assets.py`. |
| `pnpm: command not found` | Run `corepack enable` or `npm install -g pnpm`. |
