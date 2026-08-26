#!/bin/sh
set -e

echo "Waiting for MySQL at ${DB_HOST:-daykin_db}:${DB_PORT:-3306}..."
until python -c "
import socket, sys, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect((os.environ.get('DB_HOST', 'daykin_db'), int(os.environ.get('DB_PORT', 3306))))
    s.close()
except Exception:
    sys.exit(1)
"; do
  echo "MySQL not ready yet — retrying in 2s..."
  sleep 2
done

echo "MySQL is up — running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn daykin_backend.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -