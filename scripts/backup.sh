#!/usr/bin/env bash
# Nightly backup: every service database (pg_dump, compressed) plus the uploaded-files volume.
# Keeps the last $KEEP_DAYS days. Run from cron on the host, e.g.: 30 2 * * * /srv/shohorsathi/scripts/backup.sh
# Copy the backups directory off the server too (another region or offline storage).
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR=${BACKUP_DIR:-./backups}
KEEP_DAYS=${KEEP_DAYS:-14}
COMPOSE=${COMPOSE:-docker compose}
stamp=$(date +%Y%m%d-%H%M)
target="$BACKUP_DIR/$stamp"
mkdir -p "$target"
target=$(cd "$target" && pwd)   # absolute, so the volume mount below works whether BACKUP_DIR is relative or absolute

user=$($COMPOSE exec -T postgres printenv POSTGRES_USER)
dbs=$($COMPOSE exec -T postgres psql -U "$user" -Atc "SELECT datname FROM pg_database WHERE datname LIKE '%\_db'")
for db in $dbs; do
  $COMPOSE exec -T postgres pg_dump -U "$user" -Fc "$db" > "$target/$db.dump"
done

# uploaded files (private files are already encrypted at rest)
$COMPOSE run --rm --no-deps -v "$target:/backup" --entrypoint tar media czf /backup/media.tar.gz -C /data media

find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP_DAYS" -exec rm -rf {} +
echo "backup written to $target ($(du -sh "$target" | cut -f1))"
