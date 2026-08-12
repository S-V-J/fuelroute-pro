#!/bin/bash
# FuelRoute Pro - Docker Entrypoint
# Handles initialization and startup tasks

set -e

echo "Starting FuelRoute Pro..."

# Wait for database if using PostgreSQL
if [ "$DATABASE_URL" != "sqlite:///db.sqlite3" ]; then
    echo "Waiting for database..."
    # Extract host and port from DATABASE_URL
    # Format: postgresql://user:pass@host:port/dbname
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')

    if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
        while ! nc -z $DB_HOST $DB_PORT; do
            sleep 1
        done
        echo "Database is ready!"
    fi
fi

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if specified
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    echo "Creating superuser..."
    python manage.py createsuperuser --noinput --username $DJANGO_SUPERUSER_USERNAME --email $DJANGO_SUPERUSER_EMAIL || true
fi

# Warm cache on production startup
if [ "${DJANGO_SETTINGS_MODULE}" = "fuelroute.settings.production" ] || [ "${DJANGO_SETTINGS_MODULE}" = "fuelroute.settings.development" ]; then
    echo "Warming route and geocode caches..."
    python manage.py warm_cache
fi

# Import fuel data if CSV exists and no stations in DB
if [ -f "data/fuel-prices-for-be-assessment.csv" ]; then
    STATION_COUNT=$(python manage.py shell -c "from core.models import Station; print(Station.objects.count())" 2>/dev/null || echo "0")
    if [ "$STATION_COUNT" = "0" ]; then
        echo "Importing fuel station data..."
        python manage.py import_stations data/fuel-prices-for-be-assessment.csv

        echo "Geocoding stations..."
        python manage.py geocode_stations
    else
        echo "Stations already exist ($STATION_COUNT), skipping import."
    fi
fi

# Execute the main command
exec "$@"
