#!/bin/bash
# entrypoint.sh — wait for DB then start uvicorn

set -e

echo "Waiting for database..."
for i in $(seq 1 30); do
    # Extract host and port from DATABASE_URL
    DB_URL="${DATABASE_URL}"
    DB_HOST=$(echo "$DB_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
    DB_PORT=$(echo "$DB_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-5432}"
    
    # Try to connect using bash /dev/tcp or curl
    if timeout 1 bash -c "echo >/dev/tcp/$DB_HOST/$DB_PORT" 2>/dev/null; then
        echo "Database is up on $DB_HOST:$DB_PORT"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "WARNING: Database not reachable after 30 attempts — starting anyway"
    fi
    echo "Attempt $i/30: Database not ready, waiting 2s..."
    sleep 2
done

echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
