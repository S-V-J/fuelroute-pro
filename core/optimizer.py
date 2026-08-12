import math
from core.models import Station

def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in miles."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def calculate_route_bbox(route_geometry: dict, buffer_miles: float) -> dict:
    """
    Calculate bounding box around route geometry expanded by buffer_miles.
    Returns dict with min_lat, max_lat, min_lon, max_lon.
    """
    coords = route_geometry.get('coordinates', [])
    if not coords:
        return {'min_lat': -90, 'max_lat': 90, 'min_lon': -180, 'max_lon': 180}

    lats = [c[1] for c in coords]
    lons = [c[0] for c in coords]

    # Approximate degree offset for buffer_miles
    # 1 degree latitude ≈ 69 miles
    # 1 degree longitude ≈ 69 * cos(lat) miles
    lat_buffer = buffer_miles / 69.0
    avg_lat = sum(lats) / len(lats)
    lon_buffer = buffer_miles / (69.0 * math.cos(math.radians(avg_lat))) if abs(avg_lat) < 89 else buffer_miles

    return {
        'min_lat': min(lats) - lat_buffer,
        'max_lat': max(lats) + lat_buffer,
        'min_lon': min(lons) - lon_buffer,
        'max_lon': max(lons) + lon_buffer,
    }


def get_candidate_stations(route_geometry: dict, buffer_miles: float, total_distance_miles: float) -> list:
    """
    Filters stations to those within `buffer_miles` of the route geometry.
    Returns a list of stations sorted by their distance along the route.

    Performance optimizations:
    1. Bbox pre-filter in DB query to avoid loading all stations
    2. Price/state validation to skip invalid stations early
    3. Strided closest-point search: coarse scan every N points, then refine nearby
       to avoid O(stations × route_points) full scan.
    """
    coords = route_geometry.get('coordinates', [])
    if not coords:
        return []

    # Pre-calculate cumulative distances along route
    cumulative_distances = [0.0]
    for i in range(1, len(coords)):
        dist = haversine_miles(coords[i-1][1], coords[i-1][0], coords[i][1], coords[i][0])
        cumulative_distances.append(cumulative_distances[-1] + dist)

    # Bbox pre-filter: query only stations in route corridor
    # Also filter out invalid prices and non-US states at the DB level
    bbox = calculate_route_bbox(route_geometry, buffer_miles)
    stations = Station.objects.filter(
        latitude__gte=bbox['min_lat'],
        latitude__lte=bbox['max_lat'],
        longitude__gte=bbox['min_lon'],
        longitude__lte=bbox['max_lon'],
        latitude__isnull=False,
        longitude__isnull=False,
        retail_price__gt=0,  # Skip zero/negative prices
    )

    # Pre-compute a strided index for fast closest-point lookup
    # For long routes, checking every point per station is O(N*M).
    # We use stride=5 for the coarse pass, then refine ±5 points around the best candidate.
    stride = max(1, len(coords) // 200)  # Adaptive stride: ~200 coarse samples max
    coarse_coords = coords[::stride]
    coarse_dists = cumulative_distances[::stride]

    candidates = []
    for station in stations:
        # Skip non-US states (defensive; import command already filters these)
        if station.state and len(station.state) == 2 and station.state.upper() not in _US_STATES:
            continue

        # Coarse pass: find approximate closest point using strided samples
        min_offset = float('inf')
        best_coarse_idx = 0
        for j, point in enumerate(coarse_coords):
            offset = haversine_miles(station.latitude, station.longitude, point[1], point[0])
            if offset < min_offset:
                min_offset = offset
                best_coarse_idx = j

        # If even the coarse closest point is beyond buffer, skip entirely
        if min_offset > buffer_miles:
            continue

        # Refine pass: check points around the best coarse index
        # Map coarse index back to original coord index range
        refine_start = max(0, best_coarse_idx * stride - stride)
        refine_end = min(len(coords), (best_coarse_idx + 1) * stride + stride)
        refined_offset = min_offset
        refined_route_dist = coarse_dists[best_coarse_idx]

        for k in range(refine_start, refine_end):
            offset = haversine_miles(station.latitude, station.longitude, coords[k][1], coords[k][0])
            if offset < refined_offset:
                refined_offset = offset
                refined_route_dist = cumulative_distances[k]

        if refined_offset <= buffer_miles:
            candidates.append({
                'station': station,
                'offset_miles': refined_offset,
                'route_distance': refined_route_dist,
                'price': float(station.retail_price)
            })

    candidates.sort(key=lambda x: x['route_distance'])
    return candidates


# US states set for filtering (50 states + DC)
_US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC',
}

def _dedupe_same_marker(candidates: list, tolerance: float = 0.5) -> list:
    """
    When multiple stations fall within `tolerance` miles of the same route position,
    keep only the cheapest one to avoid redundant stops at the same mile marker.
    """
    if not candidates:
        return candidates
    grouped = []
    for c in sorted(candidates, key=lambda x: x['route_distance']):
        placed = False
        for g in grouped:
            if abs(g['route_distance'] - c['route_distance']) <= tolerance:
                if c['price'] < g['price']:
                    g['station'] = c['station']
                    g['price'] = c['price']
                    g['offset_miles'] = c['offset_miles']
                placed = True
                break
        if not placed:
            grouped.append(dict(c))
    return grouped


def optimize_fuel_stops(
    total_distance_miles: float,
    candidates: list,
    range_miles: float = 500.0,
    mpg: float = 10.0,
    start_fuel_gallons: float = 0.0
) -> dict:
    """
    Greedy fuel optimization algorithm.

    Strategy:
    - Vehicle capacity = range_miles / mpg (gallons)
    - At each fueling point, look ahead to all stations reachable with a full tank
    - If a cheaper station is reachable, buy just enough to reach the cheapest such station
    - If no cheaper station is reachable, fill the tank (or buy enough to reach destination)
    - Handle virtual start (0 fuel) by treating the cheapest reachable station as the first fueling point
    """
    if total_distance_miles <= 0:
        return {'stops': [], 'total_gallons': 0.0, 'total_cost': 0.0, 'warnings': ['Route distance must be positive.']}

    if range_miles <= 0 or mpg <= 0:
        return {'stops': [], 'total_gallons': 0.0, 'total_cost': 0.0, 'warnings': ['Invalid vehicle configuration: range and MPG must be positive.']}

    tank_capacity = range_miles / mpg

    if total_distance_miles > 3000:
        warnings = [f"Route distance ({total_distance_miles:.1f} mi) exceeds expected US max — verify start/finish locations are correct."]
    else:
        warnings = []

    stops = []
    total_gallons_purchased = 0.0
    total_cost = 0.0

    # Deduplicate stations at the same mile marker (keep cheapest)
    candidates = _dedupe_same_marker(candidates, tolerance=0.5)

    # Warn about suspicious prices
    for c in candidates:
        if c['station'] is not None:
            price = c['price']
            if price < 1.0:
                warnings.append(f"Station '{c['station'].name}' has suspiciously low price (${price:.2f}/gal) — verify data.")
            elif price > 10.0:
                warnings.append(f"Station '{c['station'].name}' has high price (${price:.2f}/gal).")

    # Add virtual destination
    candidates = candidates + [{
        'station': None,
        'route_distance': total_distance_miles,
        'price': 0.0,
        'is_destination': True
    }]

    current_fuel = start_fuel_gallons
    current_position = 0.0  # miles from start
    current_price = None  # price at current fueling location
    current_station = None
    current_idx = 0

    # Handle virtual start: if starting with 0 fuel, we must "buy" at the first station
    if current_fuel <= 0:
        # Find all stations reachable from start (position 0) with a full tank
        # Exclude stations at or very near the destination (within 1 mile)
        reachable_from_start = []
        for c in candidates:
            if c['station'] is None:
                continue
            # Skip stations at the destination
            if c['route_distance'] >= total_distance_miles - 1.0:
                continue
            dist = c['route_distance'] - current_position
            fuel_needed = dist / mpg
            if fuel_needed <= tank_capacity:
                reachable_from_start.append(c)

        if not reachable_from_start:
            warnings.append(f"No fuel stations reachable from start within {range_miles} miles.")
            return {
                'stops': stops,
                'total_gallons': round(total_gallons_purchased, 2),
                'total_cost': round(total_cost, 2),
                'warnings': warnings
            }

        # Choose the cheapest reachable station as virtual start
        # If multiple have same price, prefer the one closer to start
        virtual_start = min(reachable_from_start, key=lambda x: (x['price'], x['route_distance']))
        dist_to_virtual = virtual_start['route_distance'] - current_position
        fuel_needed = dist_to_virtual / mpg

        # Buy fuel at virtual start station's price
        cost = fuel_needed * virtual_start['price']

        # Only add stop if we're actually buying fuel (fuel_needed > 0)
        if fuel_needed > 0:
            stops.append({
                'station_id': virtual_start['station'].id,
                'station_name': f"{virtual_start['station'].name} (Virtual Start)" if dist_to_virtual > 0 else virtual_start['station'].name,
                'price_per_gallon': round(virtual_start['price'], 2),
                'gallons_purchased': round(fuel_needed, 2),
                'cost_usd': round(cost, 2),
                'route_distance': round(virtual_start['route_distance'], 2)
            })
            total_gallons_purchased += fuel_needed
            total_cost += cost

        # After driving to virtual start, fuel is consumed
        current_fuel = 0.0  # Arrive with empty tank
        current_position = virtual_start['route_distance']
        current_price = virtual_start['price']
        current_station = virtual_start['station']

        # Find index of virtual start in candidates
        current_idx = next(i for i, c in enumerate(candidates) if c['station'] and c['station'].id == virtual_start['station'].id)
    else:
        # Starting with fuel - assume at position 0
        current_idx = 0
        current_price = candidates[0]['price'] if candidates[0]['station'] else 0
        current_station = candidates[0]['station'] if candidates[0]['station'] else None

    # Main optimization loop
    while current_position < total_distance_miles:
        # Check if we can reach destination with current fuel
        dist_to_dest = total_distance_miles - current_position
        fuel_to_dest = dist_to_dest / mpg

        if fuel_to_dest <= current_fuel:
            # Can reach destination, done
            break

        # Find all stations reachable with a full tank from current position
        max_reach_distance = current_position + range_miles
        reachable = []
        for i in range(current_idx + 1, len(candidates)):
            c = candidates[i]
            if c['route_distance'] > max_reach_distance:
                break
            if c['station'] is None:
                # Destination is reachable with full tank
                reachable.append(c)
                break
            # Skip stations at the destination
            if c['route_distance'] >= total_distance_miles - 1.0:
                continue
            reachable.append(c)

        if not reachable:
            warnings.append(f"Stranded: No reachable stations within {range_miles} miles from mile {current_position:.1f}.")
            break

        # Check if destination is in reachable and we can reach it with current fuel
        dest_in_reachable = any(c['station'] is None for c in reachable)
        if dest_in_reachable and fuel_to_dest <= current_fuel:
            break

        # Find cheaper stations ahead (excluding destination)
        cheaper_stations = [c for c in reachable if c['station'] and c['price'] < current_price]

        if cheaper_stations:
            # Buy just enough to reach the cheapest cheaper station
            next_station = min(cheaper_stations, key=lambda x: x['price'])
            dist_to_next = next_station['route_distance'] - current_position
            fuel_needed = dist_to_next / mpg
            fuel_to_buy = fuel_needed - current_fuel

            if fuel_to_buy > 0:
                cost = fuel_to_buy * current_price
                stops.append({
                    'station_id': current_station.id if current_station else next_station['station'].id,
                    'station_name': current_station.name if current_station else next_station['station'].name,
                    'price_per_gallon': round(current_price, 2),
                    'gallons_purchased': round(fuel_to_buy, 2),
                    'cost_usd': round(cost, 2),
                    'route_distance': round(current_position, 2)
                })
                total_gallons_purchased += fuel_to_buy
                total_cost += cost
                current_fuel += fuel_to_buy

            # Drive to next station (consume fuel)
            current_fuel -= fuel_needed
            current_position = next_station['route_distance']
            current_price = next_station['price']
            current_station = next_station['station']
            current_idx = candidates.index(next_station)
        else:
            # No cheaper station ahead - fill tank (or buy enough to reach destination)
            # Check if destination is reachable with full tank
            if dest_in_reachable:
                # Buy just enough to reach destination
                fuel_to_buy = fuel_to_dest - current_fuel
                if fuel_to_buy > 0:
                    cost = fuel_to_buy * current_price
                    stops.append({
                        'station_id': current_station.id if current_station else None,
                        'station_name': current_station.name if current_station else 'Unknown',
                        'price_per_gallon': round(current_price, 2),
                        'gallons_purchased': round(fuel_to_buy, 2),
                        'cost_usd': round(cost, 2),
                        'route_distance': round(current_position, 2)
                    })
                    total_gallons_purchased += fuel_to_buy
                    total_cost += cost
                break
            else:
                # Fill the tank
                fuel_to_buy = tank_capacity - current_fuel
                if fuel_to_buy > 0:
                    cost = fuel_to_buy * current_price
                    stops.append({
                        'station_id': current_station.id if current_station else None,
                        'station_name': current_station.name if current_station else 'Unknown',
                        'price_per_gallon': round(current_price, 2),
                        'gallons_purchased': round(fuel_to_buy, 2),
                        'cost_usd': round(cost, 2),
                        'route_distance': round(current_position, 2)
                    })
                    total_gallons_purchased += fuel_to_buy
                    total_cost += cost
                    current_fuel = tank_capacity

                # Move to the next station - choose the cheapest one in reachable
                next_station = min([c for c in reachable if c['station']], key=lambda x: x['price'])
                dist_to_next = next_station['route_distance'] - current_position
                current_fuel -= dist_to_next / mpg
                current_position = next_station['route_distance']
                current_price = next_station['price']
                current_station = next_station['station']
                current_idx = candidates.index(next_station)

    return {
        'stops': stops,
        'total_gallons': round(total_gallons_purchased, 2),
        'total_cost': round(total_cost, 2),
        'warnings': warnings
    }