#!/usr/bin/env bash
# Build and start the whole backend (14 Django services, workers, Postgres, Redis, nginx gateway),
# wait until it answers, and optionally load the demo data.
#   scripts/up.sh            # build + start
#   scripts/up.sh --demo     # ... and load demo data (skipped if it is already there)
set -euo pipefail
cd "$(dirname "$0")/.."

for tool in docker python3 openssl curl; do
  command -v "$tool" >/dev/null || { echo "missing: $tool (see SETUP.md)"; exit 1; }
done
docker compose version >/dev/null 2>&1 || { echo "missing: Docker Compose v2 ('docker compose')"; exit 1; }

[ -f .env ] || { cp .env.example .env; echo "created .env from .env.example"; }
./scripts/gen-jwt-keys.sh

# One image at a time: building all of them in parallel needs more than 8 GB of RAM.
services=$(docker compose config --format json | python3 -c 'import json,sys; print(" ".join(n for n, s in json.load(sys.stdin)["services"].items() if "build" in s))')
total=$(echo "$services" | wc -w); i=0
for s in $services; do
  i=$((i + 1)); echo "[$i/$total] building $s"
  docker compose build -q "$s"
done

docker compose up -d
gateway="http://localhost:$(grep -E '^GATEWAY_PORT=' .env | cut -d= -f2 || true)"
[ "$gateway" = "http://localhost:" ] && gateway="http://localhost:8088"
echo "waiting for the services to answer on $gateway ..."
for _ in $(seq 1 100); do
  ok=1
  for path in /api/services/ /api/areas/ /api/issues/ /api/subscription-plans/ /api/community/posts/; do
    [ "$(curl -s -o /dev/null -w '%{http_code}' "$gateway$path")" = 200 ] || ok=0
  done
  [ $ok = 1 ] && break
  sleep 3
done
[ $ok = 1 ] || { echo "services did not come up; check: docker compose ps; docker compose logs <service>"; exit 1; }
echo "backend is up on $gateway"

if [ "${1:-}" = "--demo" ]; then
  if [ "$(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' \
        -d '{"phone":"01700000000","password":"demo1234"}' "$gateway/api/auth/login/")" = 200 ]; then
    echo "demo data is already loaded (to start over: docker compose down -v && scripts/up.sh --demo)"
  else
    python3 scripts/seed_demo.py "$gateway"
  fi
fi
echo "next: pnpm install (first time) and pnpm dev  → http://localhost:5173 · :5174 · :5175"
