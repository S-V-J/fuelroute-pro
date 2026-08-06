# FuelRoute Pro - Project Charter

## Mission
FuelRoute Pro helps users plan cost-efficient fuel stops along a U.S. driving route using fuel price data, route geometry, vehicle range, and fuel efficiency.

## Target Users
- Drivers
- Fleet operators
- Logistics planners
- Developers integrating route-based fuel cost planning via JSON API

## Core Features
1. Input start and finish locations within the USA.
2. Generate a driving route displayed on an interactive map.
3. Select fuel stops optimized for cost efficiency.
4. Respect configurable vehicle range (default: 500 miles).
5. Assume configurable fuel efficiency (default: 10 MPG).
6. Display total estimated fuel cost in USD.
7. Provide both an interactive web UI and a clean JSON REST API.

## Out-of-Scope Items
- Real-time traffic routing or dynamic ETA calculations.
- International routing (strictly USA for MVP).
- Live fuel price streaming (relies on imported static CSV dataset).
- Payment processing or fuel card integration.

## Assumptions
- Default vehicle assumptions: Max range 500 miles, 10 MPG fuel efficiency, 50-gallon fuel capacity, USD currency.
- The routing provider (OSRM public demo) is available and reliable for MVP.
- Users will input valid US addresses/coordinates.

## Data Source
- Fuel prices and station locations are imported from a provided OPIS Truckstop CSV dataset.
- Map tiles from OpenStreetMap.

## Routing Strategy
- Prefer exactly **one routing-API call per unique route** to minimize external dependencies and latency.
- Use OSRM public demo server by default, with adapters available for self-hosted OSRM, OpenRouteService, or GraphHopper.

## Caching Strategy
- Cache routing results aggressively based on start/end coordinate hashes.
- Cache geocoding results aggressively to prevent redundant API calls and rate limits.

## Success Metrics
- The app installs and runs out-of-the-box from a fresh GitHub clone without requiring external database setup (SQLite) or secret API keys.
- API responses return route geometry, selected stops, prices, gallons, leg distances, and total cost in < 2 seconds for cached routes.
- Graceful degradation and user-friendly errors for invalid addresses, out-of-bounds routes, or missing stations.