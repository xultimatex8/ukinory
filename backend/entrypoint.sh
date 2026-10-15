#!/bin/sh
set -e

mkdir -p /app/staticfiles
chown -R appuser:appuser /app/staticfiles

exec gosu appuser sh -c '
    python manage.py migrate
    python manage.py collectstatic --noinput
    exec "$@"
' sh "$@"