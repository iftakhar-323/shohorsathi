# Running ShohorSathi from a fresh clone

This guide takes you from `git clone` to all three web apps running with demo data (Dhaka, Chattogram and Khulna),
and shows how to check that everything works.

> **সংক্ষেপে (বাংলা):** Docker, Node.js আর Python লাগবে। রিপো ক্লোন করে `scripts/up.sh --demo` চালান — এটা সব
> ব্যাকএন্ড সার্ভিস বানিয়ে চালু করবে আর ডেমো ডেটা ভরে দেবে (প্রথমবার ১০–২০ মিনিট)। তারপর `pnpm install` আর
> `pnpm dev` চালালে তিনটা অ্যাপ খুলবে: কাস্টমার http://localhost:5173, প্রোভাইডার http://localhost:5174,
> অ্যাডমিন http://localhost:5175। সব অ্যাকাউন্টের পাসওয়ার্ড `demo1234`।

## What runs where

```
 browser ──► customer-web :5173 ─┐
         ──► provider-web :5174 ─┼─ /api, /media ──► nginx gateway :8088 ──► 14 Django services (+ Celery workers)
         ──► admin-web    :5175 ─┘                                            │
                                                         PostgreSQL :5433 (one database per service) · Redis
```

The backend (gateway, services, Postgres, Redis) runs in Docker. The three React apps run on your machine with Vite
and pass `/api` and `/media` requests to the gateway.

## 0. Requirements

| Tool | Version | Check with |
|---|---|---|
| Docker Engine (or Docker Desktop) with Compose v2 | Docker 24+, Compose 2.20+ | `docker compose version` |
| Node.js | 20 or newer | `node -v` |
| pnpm | 9 or newer (comes with Node via corepack) | `corepack enable && pnpm -v` |
| Python | 3.10 or newer | `python3 --version` |
| git, openssl, curl | any recent | |

- **Memory:** 8 GB RAM minimum, 16 GB recommended (31 containers). Disk: about 10 GB for the images.
- **Free ports:** 5433 (Postgres), 8088 (gateway), 5173, 5174, 5175 (apps). If 5433 or 8088 are taken, see Troubleshooting.
- **Windows:** use WSL 2 (Ubuntu) with Docker Desktop's WSL integration turned on, and run every command inside WSL.
- **Ubuntu quick install:**
  ```bash
  sudo apt install -y git curl openssl python3
  curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER   # log out and in again afterwards
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
  sudo corepack enable
  ```

## 1. Clone

```bash
git clone https://github.com/iftakhar-323/shohorsathi.git
cd shohorsathi
```

## 2. Start the backend with demo data

```bash
scripts/up.sh --demo
```

This one command:

1. creates `.env` from `.env.example` (development values; never use them in production);
2. creates the JWT signing keys in `.keys/` (`scripts/gen-jwt-keys.sh`);
3. builds the 28 service images **one at a time** (10–20 minutes the first time; later runs reuse the cache);
4. starts everything with `docker compose up -d` and waits until the gateway answers;
5. runs `scripts/seed_demo.py`, which copies the demo photos into the media volume and creates the demo data.
   Running it again later does nothing if the demo data is already there.

You should end with lines like:

```
  ✓ Khulna: 14 orders across every service type (6 done and reviewed, 3 confirmed, 3 waiting for a provider, 2 product orders)
  ✓ Khulna: 5 authorities with feed links, 16 photo issues of all 8 kinds in 15 areas, 9 community posts
  ✓ analytics history: ... synthetic facts over 8 weeks
Demo data ready. Password for every account: demo1234
backend is up on http://localhost:8088
```

<details>
<summary>Doing the same steps by hand</summary>

```bash
cp .env.example .env
./scripts/gen-jwt-keys.sh
docker compose build auth            # repeat for each service, or `docker compose build` if you have 16 GB+ RAM
docker compose up -d
docker compose ps                    # all containers "Up"; the services run their migrations on start
python3 scripts/seed_demo.py         # once the gateway answers: curl http://localhost:8088/api/services/
```
</details>

## 3. Start the three web apps

In a second terminal, from the project folder:

```bash
pnpm install          # first time only
pnpm dev              # starts all three apps; Ctrl+C stops them
```

| App | Open | Log in with (password `demo1234`) |
|---|---|---|
| Customer site | http://localhost:5173 | Dhaka: `01711000001` রহিম · `01711000002` নুসরাত · `01711000003` তানভীর<br>Khulna: `01711000004` ফারহানা · `01711000005` আরিফ · `01711000006` সুমাইয়া · `01711000007` রাকিব · `01711000008` তাসলিমা |
| Provider portal | http://localhost:5174 | Dhaka: `01811000001` করিম (electrician) · `01811000002` সালমা (cleaner) · `01811000003` জামাল (AC)<br>Khulna: `01811000004` মাসুদ (electrician) · `01811000005` রেহানা (cleaner) · `01811000006` সাইফুল (AC & plumbing) · `01811000007` নাজমুল (painter & shifting) |
| Admin panel | http://localhost:5175 | `01700000000` |

One app only: `pnpm dev:customer`, `pnpm dev:provider` or `pnpm dev:admin`.
A walkthrough for presenting is in [DEMO.md](DEMO.md).

## 4. Check that everything works

**Quick look (2 minutes):**

- http://localhost:5173 shows the Bangla home page with photos; the `English` button switches language.
- The city picker in the header lists ঢাকা, চট্টগ্রাম, খুলনা.
- http://localhost:5173/issues lists Dhaka and Khulna reports with photos; http://localhost:5173/transparency lists the authorities.
- Log in at http://localhost:5175 as `01700000000` → *অ্যানালিটিক্স* shows charts.

**Automated checks:**

```bash
# every page of the three apps in a real browser: fails on JavaScript errors, failed API calls or broken photos,
# and saves a screenshot of each page in apps/e2e/test-results/tour/
pnpm --filter e2e exec playwright install --with-deps chromium     # first time only
pnpm --filter e2e exec playwright test tests/demo-tour.spec.ts

# backend unit tests of one service (any of the 14)
docker compose exec order pytest

# end-to-end API flows through the gateway (each adds its own test records to the database)
python3 scripts/e2e_phase1.py      # … up to e2e_phase9.py

pnpm build && pnpm check:i18n      # type-check and build the apps; every Bangla string has an English version
```

The browser tour expects the demo data as `seed_demo.py` leaves it. After running the `e2e_phase*` scripts, start
from fresh demo data (next section) before presenting.

## 5. Everyday commands

| What | Command |
|---|---|
| Stop everything (keeps data) | `docker compose stop` (and Ctrl+C in the `pnpm dev` terminal) |
| Start again | `docker compose start` then `pnpm dev` |
| See what is running | `docker compose ps` |
| Logs of one service | `docker compose logs -f order` |
| OTP code for a new sign-up (dev) | `docker compose logs auth \| grep "OTP for"` |
| Fresh demo data (**deletes all data**) | `docker compose down -v && scripts/up.sh --demo` |
| Back up databases and uploads | `scripts/backup.sh` (writes to `backups/`) |
| After changing a service's code | `docker compose build <service> <service>-worker && docker compose up -d <service> <service>-worker` |
| After changing `services/common` | rebuild every image: `scripts/up.sh` |

## 6. Optional settings in `.env`

- `ANTHROPIC_API_KEY` — the AI photo quote asks Claude to look at the photo. Without it, the quote comes from a keyword
  match on the description, and the page says so.
- `GATEWAY_PORT` — change if 8088 is taken (also start the apps with `GATEWAY_URL=http://localhost:<port> pnpm dev`).
- Payments use a mock gateway and SMS/WhatsApp are printed to the logs; real providers are set up in
  [docs/deploy.md](docs/deploy.md).

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `permission denied ... docker.sock` | `sudo usermod -aG docker $USER`, then log out and in again. |
| Build stops with `exit code 137` / `Killed` | Not enough memory: build one image at a time (`scripts/up.sh` already does), close other programs, or give Docker Desktop more RAM. |
| `port is already allocated` for 5433 | Another Postgres uses it: stop it, or change `"5433:5432"` in `docker-compose.yml`. |
| `port is already allocated` for 8088 | Set `GATEWAY_PORT=8090` in `.env`, run `docker compose up -d`, and start the apps with `GATEWAY_URL=http://localhost:8090 pnpm dev`. |
| `up.sh` says the services did not come up | `docker compose ps` to find a container that is not `Up`, then `docker compose logs <service>`. Usually running `scripts/up.sh` again fixes a slow first start. |
| Pages load but say the server is unavailable / 502 | The services are still starting; wait 30 seconds. Check `docker compose ps`. |
| Photos do not show | The demo photos live in the `media` volume: run `python3 scripts/seed_demo.py` once more, or `docker compose cp demo/images/. media:/data/media/public/demo`. |
| `seed_demo.py` fails with 429 | `.env` has the production OTP limit: set `OTP_THROTTLE_RATE=1000/hour` and `docker compose up -d auth`. |
| `seed_demo.py` fails half-way | Start from scratch: `docker compose down -v && scripts/up.sh --demo`. |
| `pnpm: command not found` | `corepack enable` (or `npm install -g pnpm`). |
| Login works but data is empty | The demo seed did not run: `python3 scripts/seed_demo.py`. |
