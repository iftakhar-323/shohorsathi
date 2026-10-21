#!/usr/bin/env bash
# Restore a backup made by backup.sh: ./scripts/restore.sh backups/20261021-0230 [db_name ...]
# With no database names, restores all of them and the media files. Stop the services first
# (docker compose stop) and keep postgres running. Practise this on staging regularly.
set -euo pipefail
cd "$(dirname "$0")/.."

src=${1:?usage: restore.sh <backup dir> [db ...]}
shift || true
COMPOSE=${COMPOSE:-docker compose}
user=$($COMPOSE exec -T postgres printenv POSTGRES_USER)

dbs=("$@")
if [ ${#dbs[@]} -eq 0 ]; then
  for f in "$src"/*.dump; do dbs+=("$(basename "$f" .dump)"); done
  restore_media=1
fi

for db in "${dbs[@]}"; do
  echo "restoring $db"
  $COMPOSE exec -T postgres psql -U "$user" -c "DROP DATABASE IF EXISTS $db WITH (FORCE)" -c "CREATE DATABASE $db"
  $COMPOSE exec -T postgres pg_restore -U "$user" -d "$db" --no-owner < "$src/$db.dump"
done

if [ "${restore_media:-0}" = 1 ] && [ -f "$src/media.tar.gz" ]; then
  $COMPOSE run --rm --no-deps -v "$PWD/$src:/backup:ro" --entrypoint sh media -c "rm -rf /data/media/* && tar xzf /backup/media.tar.gz -C /data"
fi
echo "restore done"
