import time
import httpx
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Station, GeocodeCache

def normalize_query(query: str) -> str:
    return " ".join(query.lower().split())

class Command(BaseCommand):
    help = 'Geocodes stations missing latitude/longitude using the Photon API (OpenStreetMap)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Limit the number of stations to geocode (0 for all)',
        )

    def handle(self, *args, **kwargs):
        limit = kwargs['limit']
        stations = Station.objects.filter(latitude__isnull=True)

        if limit > 0:
            stations = stations[:limit]

        total = stations.count()
        self.stdout.write(f"📍 Found {total} stations requiring geocoding.")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("✅ All stations already geocoded."))
            return

        photon_url = getattr(settings, 'PHOTON_GEOCODE_URL', 'https://photon.komoot.io/api/')

        success_count = 0
        fail_count = 0

        # CRITICAL: Photon API requires a valid User-Agent and uses 'countrycode' (SINGULAR), NOT 'countrycodes'
        headers = {
            'User-Agent': 'FuelRoutePro/1.0 (https://github.com/S-V-J/fuelroute-pro; stjl093@gmail.com)'
        }

        with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
            for index, station in enumerate(stations, 1):
                # Clean the name to avoid comma-confusion in the query string
                clean_name = station.name.replace(',', '').strip()
                query = f"{clean_name}, {station.city}, {station.state}"
                norm_query = normalize_query(query)

                # FIX: Use 'countrycode' (singular)
                params = {'q': query, 'limit': 1, 'countrycode': 'us', 'lang': 'en'}

                try:
                    response = client.get(photon_url, params=params)

                    coords = None
                    raw_response = None
                    if response.status_code == 400 or not response.json().get('features'):
                        # Fallback: If specific name fails, search just City + State
                        query_fb = f"{station.city}, {station.state}"
                        params_fb = {'q': query_fb, 'limit': 1, 'countrycode': 'us', 'lang': 'en'}
                        res_fb = client.get(photon_url, params=params_fb)

                        if res_fb.status_code == 200 and res_fb.json().get('features'):
                            coords = res_fb.json()['features'][0]['geometry']['coordinates']
                            raw_response = res_fb.json()
                    else:
                        response.raise_for_status()
                        data = response.json()
                        raw_response = data
                        if data.get('features'):
                            coords = data['features'][0]['geometry']['coordinates']

                    if coords:
                        # Photon returns [longitude, latitude] in GeoJSON format
                        station.longitude = float(coords[0])
                        station.latitude = float(coords[1])
                        station.save(update_fields=['latitude', 'longitude', 'updated_at'])
                        success_count += 1
                        self.stdout.write(f"[{index}/{total}] ✅ {station.name} -> ({station.latitude:.4f}, {station.longitude:.4f})")

                        # Create GeocodeCache entry
                        GeocodeCache.objects.update_or_create(
                            normalized_query=norm_query,
                            provider='photon',
                            defaults={
                                'query': query,
                                'latitude': station.latitude,
                                'longitude': station.longitude,
                                'raw_response': raw_response,
                                'is_success': True
                            }
                        )
                    else:
                        fail_count += 1
                        self.stdout.write(self.style.WARNING(f"[{index}/{total}] ⚠️ No coordinates found for: {station.name}"))

                        # Cache the failure too
                        GeocodeCache.objects.update_or_create(
                            normalized_query=norm_query,
                            provider='photon',
                            defaults={
                                'query': query,
                                'raw_response': raw_response or {},
                                'is_success': False
                            }
                        )

                except httpx.HTTPError as e:
                    fail_count += 1
                    self.stdout.write(self.style.ERROR(f"[{index}/{total}] ❌ HTTP Error for {station.name}: {e}"))

                    # Cache the error
                    GeocodeCache.objects.update_or_create(
                        normalized_query=norm_query,
                        provider='photon',
                        defaults={
                            'query': query,
                            'raw_response': {'error': str(e)},
                            'is_success': False
                        }
                    )
                except Exception as e:
                    fail_count += 1
                    self.stdout.write(self.style.ERROR(f"[{index}/{total}] ❌ Exception for {station.name}: {str(e)}"))

                    # Cache the error
                    GeocodeCache.objects.update_or_create(
                        normalized_query=norm_query,
                        provider='photon',
                        defaults={
                            'query': query,
                            'raw_response': {'error': str(e)},
                            'is_success': False
                        }
                    )

                # Rate limit respect: 0.2s delay prevents IP bans on free tiers
                time.sleep(0.2)

        self.stdout.write(self.style.SUCCESS(f"\n🎉 Geocoding complete. Success: {success_count} | Failed: {fail_count}"))