import time
import logging
from django.core.management.base import BaseCommand
from django.db import connection
from core.services import get_driving_route, geocode_location

logger = logging.getLogger(__name__)

COMMON_ROUTES = [
    ("Chicago, IL", "Dallas, TX"),
    ("Los Angeles, CA", "Phoenix, AZ"),
    ("Atlanta, GA", "Miami, FL"),
    ("New York, NY", "Philadelphia, PA"),
    ("Seattle, WA", "Portland, OR"),
    ("Denver, CO", "Salt Lake City, UT"),
    ("Houston, TX", "San Antonio, TX"),
]


class Command(BaseCommand):
    help = "Pre-warm route and geocode caches for common routes"

    def handle(self, *args, **options):
        self.stdout.write("Starting cache warming...")
        geo_success = 0
        geo_fail = 0
        route_success = 0
        route_fail = 0

        for start, finish in COMMON_ROUTES:
            self.stdout.write(f"  Geocoding: {start}")
            start_geo = geocode_location(start)
            if start_geo['success']:
                geo_success += 1
            else:
                geo_fail += 1
                self.stdout.write(self.style.WARNING(f"    Failed: {start_geo.get('error')}"))
                continue

            self.stdout.write(f"  Geocoding: {finish}")
            finish_geo = geocode_location(finish)
            if finish_geo['success']:
                geo_success += 1
            else:
                geo_fail += 1
                self.stdout.write(self.style.WARNING(f"    Failed: {finish_geo.get('error')}"))
                continue

            self.stdout.write(f"  Routing: {start} → {finish}")
            route_data = get_driving_route(start_geo['lat'], start_geo['lon'], finish_geo['lat'], finish_geo['lon'])
            if route_data['success']:
                route_success += 1
                self.stdout.write(self.style.SUCCESS(f"    Cached ({route_data['distance_miles']:.1f} mi)"))
            else:
                route_fail += 1
                self.stdout.write(self.style.WARNING(f"    Failed: {route_data.get('error')}"))

            time.sleep(0.2)

        self.stdout.write(self.style.SUCCESS(
            f"Cache warming complete: {geo_success} geocodes, {route_success} routes cached. "
            f"Failures: {geo_fail} geocode, {route_fail} route."
        ))
