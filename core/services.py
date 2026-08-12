import time
import httpx
import hashlib
import json
import uuid
import logging
from django.conf import settings
from django.db import transaction
from core.models import Station, GeocodeCache, RouteCache, RoutePlan, RouteStop
from core.optimizer import get_candidate_stations, optimize_fuel_stops

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple circuit breaker to prevent cascade failures from upstream providers."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure: float = 0.0
        self.open: bool = False

    def allow_request(self) -> bool:
        if self.open and (time.time() - self.last_failure) > self.recovery_timeout:
            self.open = False
            self.failures = 0
            logger.info("Circuit breaker closed — allowing requests again.")
            return True
        return not self.open

    def record_success(self):
        self.failures = 0
        self.open = False

    def record_failure(self):
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.failure_threshold:
            self.open = True
            logger.error(f"Circuit breaker opened after {self.failures} failures.")


OSRM_CIRCUIT_BREAKER = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
PHOTON_CIRCUIT_BREAKER = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
CENSUS_CIRCUIT_BREAKER = CircuitBreaker(failure_threshold=3, recovery_timeout=120)
ORS_CIRCUIT_BREAKER = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
GRAPHHOPPER_CIRCUIT_BREAKER = CircuitBreaker(failure_threshold=5, recovery_timeout=60)


def normalize_query(query: str) -> str:
    # Replace commas with space, then normalize whitespace
    query = query.replace(',', ' ')
    return " ".join(query.lower().split())


# ============================================================================
# PROVIDER ABSTRACTIONS
# ============================================================================

class RoutingProvider:
    """Base class for routing providers."""
    def route(self, start_lat: float, start_lon: float, finish_lat: float, finish_lon: float) -> dict:
        raise NotImplementedError


class GeocodeProvider:
    """Base class for geocoding providers."""
    def geocode(self, query: str) -> dict:
        raise NotImplementedError


# ============================================================================
# GEOCODING PROVIDERS
# ============================================================================

def geocode_location(query: str) -> dict:
    """Main geocode function with circuit breaker and fallback chain."""
    norm_query = normalize_query(query)
    cached = GeocodeCache.objects.filter(normalized_query=norm_query, provider='photon').first()
    if cached and cached.is_success:
        return {'success': True, 'lat': cached.latitude, 'lon': cached.longitude, 'display_name': cached.query, 'cached': True}

    photon_url = getattr(settings, 'PHOTON_GEOCODE_URL', 'https://photon.komoot.io/api/')
    headers = {'User-Agent': 'FuelRoutePro/1.0 (https://github.com/S-V-J/fuelroute-pro; stjl093@gmail.com)'}
    params = {'q': query, 'limit': 1, 'countrycode': 'us', 'lang': 'en'}

    if not PHOTON_CIRCUIT_BREAKER.allow_request():
        logger.warning("Photon circuit breaker open — using Census fallback.")
        return _geocode_fallback_census(query, norm_query)

    for attempt in range(2):
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
                response = client.get(photon_url, params=params)

            if response.status_code == 400:
                raise httpx.HTTPStatusError("400 Bad Request", request=response.request, response=response)

            response.raise_for_status()
            data = response.json()
            if data.get('features'):
                feature = data['features'][0]
                coords = feature['geometry']['coordinates']
                lon, lat = float(coords[0]), float(coords[1])
                display_name = feature['properties'].get('name', query)
                GeocodeCache.objects.create(query=query, normalized_query=norm_query, latitude=lat, longitude=lon, provider='photon', raw_response=data, is_success=True)
                PHOTON_CIRCUIT_BREAKER.record_success()
                return {'success': True, 'lat': lat, 'lon': lon, 'display_name': display_name, 'cached': False}

            GeocodeCache.objects.create(query=query, normalized_query=norm_query, provider='photon', raw_response=data, is_success=False)
            return {'success': False, 'error': 'Location not found'}
        except httpx.HTTPStatusError as e:
            if attempt == 0:
                logger.info("Photon HTTP error — trying Census fallback.")
                return _geocode_fallback_census(query, norm_query)
            PHOTON_CIRCUIT_BREAKER.record_failure()
            GeocodeCache.objects.create(query=query, normalized_query=norm_query, provider='photon', raw_response={'error': str(e)}, is_success=False)
            return {'success': False, 'error': f'HTTP Error: {str(e)}'}
        except httpx.HTTPError as e:
            if attempt == 0:
                time.sleep(0.5)
                continue
            PHOTON_CIRCUIT_BREAKER.record_failure()
            GeocodeCache.objects.create(query=query, normalized_query=norm_query, provider='photon', raw_response={'error': str(e)}, is_success=False)
            return {'success': False, 'error': f'HTTP Error: {str(e)}'}
        except Exception as e:
            PHOTON_CIRCUIT_BREAKER.record_failure()
            return {'success': False, 'error': f'Exception: {str(e)}'}
    return {'success': False, 'error': 'Geocoding failed after retries.'}


def _geocode_fallback_census(query: str, norm_query: str) -> dict:
    """Fallback to US Census geocoder."""
    census_url = getattr(settings, 'CENSUS_GEOCODE_URL', 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress')
    params = {'address': query, 'benchmark': 'Public_AR_Current', 'format': 'json'}

    if not CENSUS_CIRCUIT_BREAKER.allow_request():
        logger.warning("Census circuit breaker open — geocode unavailable.")
        GeocodeCache.objects.create(query=query, normalized_query=norm_query, provider='census', raw_response={}, is_success=False)
        return {'success': False, 'error': 'Location not found (all geocoders unavailable)'}

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(census_url, params=params)
        response.raise_for_status()
        data = response.json()
        matches = data.get('result', {}).get('addressMatches', [])
        if matches:
            coords = matches[0]['coordinates']
            lon, lat = float(coords['x']), float(coords['y'])
            GeocodeCache.objects.create(query=query, normalized_query=norm_query, latitude=lat, longitude=lon, provider='census', raw_response=data, is_success=True)
            CENSUS_CIRCUIT_BREAKER.record_success()
            return {'success': True, 'lat': lat, 'lon': lon, 'display_name': query, 'cached': False}
    except Exception:
        CENSUS_CIRCUIT_BREAKER.record_failure()
        pass

    # Both failed
    GeocodeCache.objects.create(query=query, normalized_query=norm_query, provider='census', raw_response={}, is_success=False)
    return {'success': False, 'error': 'Location not found'}


# ============================================================================
# ROUTING PROVIDERS
# ============================================================================

def get_driving_route(start_lat: float, start_lon: float, finish_lat: float, finish_lon: float) -> dict:
    """Main routing function with provider chain."""
    slat, slon = round(start_lat, 5), round(start_lon, 5)
    flat, flon = round(finish_lat, 5), round(finish_lon, 5)

    # Provider chain: self-hosted OSRM -> ORS -> GraphHopper -> public OSRM
    providers = _get_routing_providers()

    for provider_name, provider_config in providers:
        if provider_name == 'osrm_local' and not OSRM_CIRCUIT_BREAKER.allow_request():
            logger.warning("Self-hosted OSRM circuit breaker open — trying next provider.")
            continue
        elif provider_name == 'openrouteservice' and not ORS_CIRCUIT_BREAKER.allow_request():
            logger.warning("ORS circuit breaker open — trying next provider.")
            continue
        elif provider_name == 'graphhopper' and not GRAPHHOPPER_CIRCUIT_BREAKER.allow_request():
            logger.warning("GraphHopper circuit breaker open — trying next provider.")
            continue

        # Check cache first
        route_string = f"{slat},{slon}|{flat},{flon}|{provider_name}"
        route_hash = hashlib.sha256(route_string.encode('utf-8')).hexdigest()
        cached_route = RouteCache.objects.filter(route_hash=route_hash).first()
        if cached_route:
            logger.info(f"Route cache hit for {provider_name}")
            return {'success': True, 'distance_miles': cached_route.distance_miles, 'duration_minutes': cached_route.duration_minutes, 'geometry': cached_route.geometry_geojson, 'cached': True}

        # Try the provider
        result = _try_routing_provider(provider_name, provider_config, slat, slon, flat, flon)
        if result['success']:
            # Cache the result
            RouteCache.objects.create(
                route_hash=route_hash, start_lat=slat, start_lon=slon,
                finish_lat=flat, finish_lon=flon, distance_miles=result['distance_miles'],
                duration_minutes=result['duration_minutes'], geometry_geojson=result['geometry'], provider=provider_name
            )
            _record_provider_success(provider_name)
            return result

    # All providers failed
    return {'success': False, 'error': 'All routing providers unavailable'}


def _get_routing_providers():
    """Get ordered list of routing providers from settings."""
    providers = []

    # 1. Self-hosted OSRM (preferred)
    osrm_local_url = getattr(settings, 'OSRM_SELF_HOSTED_URL', '')
    if osrm_local_url:
        providers.append(('osrm_local', {'url': osrm_local_url}))

    # 2. OpenRouteService
    ors_key = getattr(settings, 'OPENROUTESERVICE_API_KEY', '')
    if ors_key:
        providers.append(('openrouteservice', {'api_key': ors_key}))

    # 3. GraphHopper
    gh_key = getattr(settings, 'GRAPHHOPPER_API_KEY', '')
    if gh_key:
        providers.append(('graphhopper', {'api_key': gh_key}))

    # 4. Public OSRM (always available as last resort)
    osrm_public_url = getattr(settings, 'OSRM_PUBLIC_URL', 'https://router.project-osrm.org')
    providers.append(('osrm_public', {'url': osrm_public_url}))

    return providers


def _try_routing_provider(provider_name: str, config: dict, slat: float, slon: float, flat: float, flon: float) -> dict:
    """Try a specific routing provider."""
    for attempt in range(2):
        try:
            if provider_name == 'osrm_local':
                return _route_osrm(config['url'], slat, slon, flat, flon)
            elif provider_name == 'openrouteservice':
                return _route_ors(config['api_key'], slat, slon, flat, flon)
            elif provider_name == 'graphhopper':
                return _route_graphhopper(config['api_key'], slat, slon, flat, flon)
            elif provider_name == 'osrm_public':
                return _route_osrm(config['url'], slat, slon, flat, flon)
        except httpx.HTTPError as e:
            if attempt == 0:
                time.sleep(0.5)
                continue
            return {'success': False, 'error': f'HTTP Error: {str(e)}'}
        except Exception as e:
            return {'success': False, 'error': f'Exception: {str(e)}'}
    return {'success': False, 'error': f'{provider_name} failed after retries'}


def _route_osrm(base_url: str, slat: float, slon: float, flat: float, flon: float) -> dict:
    """Route using OSRM (self-hosted or public)."""
    coords = f"{slon},{slat};{flon},{flat}"
    params = {'overview': 'full', 'geometries': 'geojson', 'steps': 'false', 'alternatives': 'false'}

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        response = client.get(f"{base_url.rstrip('/')}/route/v1/driving/{coords}", params=params)
    response.raise_for_status()
    data = response.json()
    if data.get('code') == 'Ok' and data.get('routes'):
        route = data['routes'][0]
        return {
            'success': True,
            'distance_miles': route['distance'] * 0.000621371,
            'duration_minutes': route['duration'] / 60.0,
            'geometry': route['geometry']
        }
    return {'success': False, 'error': 'OSRM returned no routes'}


def _route_ors(api_key: str, slat: float, slon: float, flat: float, flon: float) -> dict:
    """Route using OpenRouteService."""
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}
    body = {
        'coordinates': [[slon, slat], [flon, flat]],
        'geometry': True,
        'geometry_format': 'geojson',
        'instructions': False,
    }

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        response = client.post(url, json=body, headers=headers)
    response.raise_for_status()
    data = response.json()
    if data.get('routes'):
        route = data['routes'][0]
        geometry = route['geometry']
        # ORS returns geometry as encoded polyline or geojson
        if isinstance(geometry, str):
            # Decode polyline if needed
            import polyline
            geometry = {'type': 'LineString', 'coordinates': [[lon, lat] for lat, lon in polyline.decode(geometry)]}
        return {
            'success': True,
            'distance_miles': route['distance'] * 0.000621371,
            'duration_minutes': route['duration'] / 60.0,
            'geometry': geometry
        }
    return {'success': False, 'error': 'ORS returned no routes'}


def _route_graphhopper(api_key: str, slat: float, slon: float, flat: float, flon: float) -> dict:
    """Route using GraphHopper."""
    url = "https://graphhopper.com/api/1/route"
    params = {
        'point': [f"{slat},{slon}", f"{flat},{flon}"],
        'vehicle': 'car',
        'locale': 'en',
        'calc_points': 'true',
        'points_encoded': 'false',
        'key': api_key,
    }

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        response = client.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    if data.get('paths'):
        path = data['paths'][0]
        # GraphHopper returns coordinates as [lon, lat] in geojson format
        geometry = path['points']
        if geometry.get('type') == 'LineString':
            coords = geometry['coordinates']
        else:
            # Decode if encoded
            import polyline
            coords = [[lon, lat] for lat, lon in polyline.decode(geometry)]
        return {
            'success': True,
            'distance_miles': path['distance'] * 0.000621371,
            'duration_minutes': path['time'] / 60000.0,  # time in ms
            'geometry': {'type': 'LineString', 'coordinates': coords}
        }
    return {'success': False, 'error': 'GraphHopper returned no routes'}


def _record_provider_success(provider_name: str):
    if provider_name == 'osrm_local':
        OSRM_CIRCUIT_BREAKER.record_success()
    elif provider_name == 'openrouteservice':
        ORS_CIRCUIT_BREAKER.record_success()
    elif provider_name == 'graphhopper':
        GRAPHHOPPER_CIRCUIT_BREAKER.record_success()
    elif provider_name == 'osrm_public':
        OSRM_CIRCUIT_BREAKER.record_success()


# ============================================================================
# ROUTE PLAN CALCULATION
# ============================================================================

def calculate_route_plan(start_query: str, finish_query: str, range_miles: float = 500.0, mpg: float = 10.0, start_fuel_gallons: float = 0.0, station_buffer_miles: float = 25.0, user=None) -> dict:
    start_geo = geocode_location(start_query)
    if not start_geo['success']:
        return {'success': False, 'error': f"Could not geocode start location: {start_geo.get('error')}"}

    finish_geo = geocode_location(finish_query)
    if not finish_geo['success']:
        return {'success': False, 'error': f"Could not geocode finish location: {finish_geo.get('error')}"}

    route_data = get_driving_route(start_geo['lat'], start_geo['lon'], finish_geo['lat'], finish_geo['lon'])
    if not route_data['success']:
        return {'success': False, 'error': f"Could not find route: {route_data.get('error')}"}

    candidates = get_candidate_stations(route_data['geometry'], station_buffer_miles, route_data['distance_miles'])
    optimization = optimize_fuel_stops(total_distance_miles=route_data['distance_miles'], candidates=candidates, range_miles=range_miles, mpg=mpg, start_fuel_gallons=start_fuel_gallons)

    plan_id = uuid.uuid4()

    # Save to database
    with transaction.atomic():
        plan = RoutePlan.objects.create(
            user=user,
            id=plan_id,
            start_query=start_query,
            start_lat=start_geo['lat'],
            start_lon=start_geo['lon'],
            finish_query=finish_query,
            finish_lat=finish_geo['lat'],
            finish_lon=finish_geo['lon'],
            distance_miles=route_data['distance_miles'],
            geometry=json.dumps(route_data['geometry']),
            assumptions={'range_miles': range_miles, 'mpg': mpg, 'start_fuel_gallons': start_fuel_gallons, 'station_buffer_miles': station_buffer_miles},
            warnings=optimization['warnings'],
            total_fuel_gallons=optimization['total_gallons'],
            total_cost_usd=optimization['total_cost']
        )

        for idx, stop in enumerate(optimization['stops']):
            station = Station.objects.get(id=stop['station_id'])
            RouteStop.objects.create(
                plan=plan,
                station=station,
                sequence=idx + 1,
                distance_from_start_miles=stop['route_distance'],
                gallons_purchased=stop['gallons_purchased'],
                cost_usd=stop['cost_usd']
            )

    return {
        'success': True,
        'plan_id': str(plan_id),
        'start': {'query': start_query, 'lat': start_geo['lat'], 'lon': start_geo['lon']},
        'finish': {'query': finish_query, 'lat': finish_geo['lat'], 'lon': finish_geo['lon']},
        'route': {'distance_miles': round(route_data['distance_miles'], 2), 'duration_minutes': round(route_data['duration_minutes'], 2), 'geometry': route_data['geometry']},
        'assumptions': {'range_miles': range_miles, 'mpg': mpg, 'start_fuel_gallons': start_fuel_gallons, 'station_buffer_miles': station_buffer_miles},
        'stops': optimization['stops'],
        'totals': {'fuel_gallons_purchased': optimization['total_gallons'], 'fuel_cost_usd': optimization['total_cost'], 'stop_count': len(optimization['stops'])},
        'warnings': optimization['warnings'],
        'cache': {'route_cached': route_data.get('cached', False), 'geocode_cached': start_geo.get('cached', False) or finish_geo.get('cached', False)}
    }