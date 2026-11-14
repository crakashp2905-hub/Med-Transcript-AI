#!/bin/sh
set -eu

: "${MED_TRANSCRIPT_APP_DB_PASSWORD:?Set a dedicated application database password}"

psql --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=app_password="$MED_TRANSCRIPT_APP_DB_PASSWORD" <<'SQL'
CREATE ROLE medscribe_app
  LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT CONNECT ON DATABASE medscribe TO medscribe_app;
GRANT USAGE, CREATE ON SCHEMA public TO medscribe_app;
SQL
