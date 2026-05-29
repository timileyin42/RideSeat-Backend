#!/bin/sh
set -e

# Run database migrations before starting the app
alembic upgrade head

# Launch whatever command was passed — gunicorn for the API,
# celery worker/beat for background services (overridden in docker-compose)
exec "$@"
