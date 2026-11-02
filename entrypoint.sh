#!/bin/sh
set -e

echo "==> FreshDash Production Backend Startup"

# Ensure data directories exist and are writable
mkdir -p /data /data/media

# If initial db.sqlite3 exists in /app but not in /data, seed the persistent volume on first boot
if [ ! -f /data/db.sqlite3 ] && [ -f /app/db.sqlite3 ]; then
    echo "==> Seeding initial SQLite3 database into persistent volume (/data/db.sqlite3)..."
    cp /app/db.sqlite3 /data/db.sqlite3
fi

# Run pending database migrations safely
echo "==> Applying database migrations..."
python manage.py migrate --noinput

# Start Gunicorn production WSGI server
echo "==> Starting Gunicorn server on 0.0.0.0:8000..."
exec gunicorn config.wsgi:application --config gunicorn.conf.py

