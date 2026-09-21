#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
umask 077
mkdir -p backups
file="backups/guanchen-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose --env-file .env -f compose.yml exec -T db pg_dump -U guanchen -d guanchen -Fc > "$file.tmp"
test -s "$file.tmp"
mv "$file.tmp" "$file"
printf 'Backup saved: %s\n' "$file"
