#!/usr/bin/env bash
# Load or verify the pinned PostgreSQL-native AdventureWorks OLTP source.
set -euo pipefail

readonly PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
readonly COMPOSE_FILE="$PROJECT_ROOT/infra/docker-compose.yml"
readonly SERVICE="postgres"
readonly DATABASE="adventureworks"
readonly USERNAME="grounded"
readonly ARCHIVE_URL="https://raw.githubusercontent.com/Azure-Samples/postgresql-samples-databases/963247e830b98e96d7114712ee794730b5b0ee5a/postgresql-adventureworks/AdventureWorksPG.gz"
readonly ARCHIVE_SHA256="d1c7f7d761daf2dece57e099f37363fe316864fbc4c5f0ea3c6ca1c702217fe5"

export GROUNDED_SOURCE_DATABASE="$DATABASE"
export GROUNDED_SOURCE_USERNAME="$USERNAME"
export GROUNDED_SOURCE_PASSWORD="grounded_local_password"

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

wait_for_postgres() {
  local attempts=30
  until compose exec -T "$SERVICE" pg_isready -U "$USERNAME" -d "$DATABASE" >/dev/null; do
    attempts=$((attempts - 1))
    if [ "$attempts" -eq 0 ]; then
      echo "PostgreSQL did not become healthy." >&2
      exit 1
    fi
    sleep 1
  done
}

verify() {
  wait_for_postgres
  compose exec -T "$SERVICE" psql -X -v ON_ERROR_STOP=1 -U "$USERNAME" -d "$DATABASE" \
    -c "
SELECT 'sales.salesorderheader' AS table_name, COUNT(*) AS row_count FROM sales.salesorderheader
UNION ALL SELECT 'sales.salesorderdetail', COUNT(*) FROM sales.salesorderdetail
UNION ALL SELECT 'sales.customer', COUNT(*) FROM sales.customer
UNION ALL SELECT 'sales.salesterritory', COUNT(*) FROM sales.salesterritory
UNION ALL SELECT 'production.product', COUNT(*) FROM production.product
UNION ALL SELECT 'production.productsubcategory', COUNT(*) FROM production.productsubcategory
UNION ALL SELECT 'production.productcategory', COUNT(*) FROM production.productcategory
UNION ALL SELECT 'person.person', COUNT(*) FROM person.person
UNION ALL SELECT 'person.emailaddress', COUNT(*) FROM person.emailaddress
ORDER BY table_name;"
}

load() {
  local work_directory archive
  work_directory=$(mktemp -d "${TMPDIR:-/tmp}/grounded-adventureworks.XXXXXX")
  trap "rm -rf -- '$work_directory'" EXIT
  archive="$work_directory/AdventureWorksPG.dump"

  compose up -d "$SERVICE"
  wait_for_postgres
  curl --fail --location --retry 3 --output "$archive" "$ARCHIVE_URL"
  echo "$ARCHIVE_SHA256  $archive" | shasum -a 256 -c -
  compose exec -T "$SERVICE" psql -X -v ON_ERROR_STOP=1 -U "$USERNAME" -d postgres \
    -c "DROP DATABASE IF EXISTS $DATABASE WITH (FORCE);"
  compose exec -T "$SERVICE" psql -X -v ON_ERROR_STOP=1 -U "$USERNAME" -d postgres \
    -c "CREATE DATABASE $DATABASE OWNER $USERNAME;"
  compose cp "$archive" "$SERVICE:/tmp/AdventureWorksPG.dump"
  compose exec -T "$SERVICE" pg_restore --no-owner --no-privileges -U "$USERNAME" -d "$DATABASE" \
    /tmp/AdventureWorksPG.dump
  verify
}

up() {
  compose up -d "$SERVICE"
}

case "${1:-load}" in
  up) up ;;
  load) load ;;
  verify) verify ;;
  *)
    echo "Usage: $0 [up|load|verify]" >&2
    exit 2
    ;;
esac
