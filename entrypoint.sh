#!/bin/bash
# entrypoint.sh — wait for DB then start uvicorn

set -e

DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:actly123@db:5432/actly}"

echo "Waiting for database to be ready..."
for i in $(seq 1 30); do
    # Extract host from DATABASE_URL
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
    DB_HOST="${DB_HOST:-db}"
    DB_PORT="${DB_PORT:-5432}"
    
    if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
        echo "Port $DB_PORT is open on $DB_HOST — database is up"
        break
    fi
    echo "Attempt $i/30: Database not ready on $DB_HOST:$DB_PORT, waiting 2s..."
    sleep 2
done

echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
