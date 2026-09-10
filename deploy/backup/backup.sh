#!/usr/bin/env bash
# Standalone job: never imports the ERP or runs its database migrations.
set -Eeuo pipefail
umask 077

fail() { printf '%s\n' "$1" >&2; exit 1; }
[[ -n "${DATABASE_URL:-}" ]] || fail 'DATABASE_URL is required.'
[[ "$DATABASE_URL" == postgres://* || "$DATABASE_URL" == postgresql://* ]] || fail 'A direct PostgreSQL connection URL is required.'
[[ -n "${S3_BUCKET_NAME:-}" ]] || fail 'S3_BUCKET_NAME is required.'
[[ -n "${AWS_DEFAULT_REGION:-}" ]] || fail 'AWS_DEFAULT_REGION is required.'
prefix="${BACKUP_PREFIX:-erp-backups}"
[[ "$prefix" =~ ^[a-zA-Z0-9][a-zA-Z0-9/_-]*$ ]] || fail 'Invalid BACKUP_PREFIX.'
prefix="${prefix%/}"
for command in pg_dump pg_restore aws sha256sum; do
    command -v "$command" >/dev/null || fail "Required tool missing: $command"
done

workdir=$(mktemp -d)
trap 'rm -rf -- "$workdir"' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
stamp=$(date -u +%Y-%m-%dT%H-%M-%SZ)
name="erp-${stamp}-${workdir##*.}.dump"
archive="$workdir/$name"
# PGDATABASE accepts a connection URI; keep it out of command arguments/logs.
export PGDATABASE="$DATABASE_URL" PGCONNECT_TIMEOUT=30
export PGSSLMODE="${PGSSLMODE:-require}"
unset DATABASE_URL
printf 'Creating consistent PostgreSQL backup...\n'
if ! pg_dump --format=custom --no-owner --no-acl --lock-wait-timeout=60000 \
    --file="$archive" 2>"$workdir/error.log"; then
    fail 'Database export failed. Check connectivity, permissions and PostgreSQL client version. No backup uploaded.'
fi
[[ -s "$archive" ]] || fail 'Database export is empty.'
pg_restore --list "$archive" >"$workdir/contents" 2>"$workdir/error.log" \
    || fail 'Archive validation failed. No backup uploaded.'
digest=$(sha256sum "$archive")
digest="${digest%% *}"
printf '%s  %s\n' "$digest" "$name" >"$archive.sha256"
aws_options=()
if [[ -n "${S3_ENDPOINT_URL:-}" ]]; then
    [[ "$S3_ENDPOINT_URL" == https://* ]] || fail 'Storage endpoint must use HTTPS.'
    aws_options+=(--endpoint-url "$S3_ENDPOINT_URL")
fi
key="$prefix/$name"
aws "${aws_options[@]}" s3 cp "$archive" "s3://$S3_BUCKET_NAME/$key" \
    --only-show-errors --sse AES256 --metadata "sha256=$digest" \
    2>"$workdir/error.log" || fail 'Backup upload failed. Check storage configuration.'
remote_size=$(aws "${aws_options[@]}" s3api head-object --bucket "$S3_BUCKET_NAME" \
    --key "$key" --query ContentLength --output text 2>"$workdir/error.log") \
    || fail 'Could not verify uploaded backup.'
local_size=$(wc -c <"$archive" | tr -d '[:space:]')
[[ "$remote_size" == "$local_size" ]] || fail 'Uploaded backup size does not match.'
aws "${aws_options[@]}" s3 cp "$archive.sha256" "s3://$S3_BUCKET_NAME/$key.sha256" \
    --only-show-errors --sse AES256 2>"$workdir/error.log" \
    || fail 'Checksum upload failed.'
printf 'Backup uploaded and size verified: %s (%s bytes)\n' "$key" "$local_size"
