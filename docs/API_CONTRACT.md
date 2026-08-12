# FuelRoute Pro — API Contract

Base URL: `/api/v1/`
Authentication: None required for MVP public endpoints.
Content-Type: `application/json`

## Endpoints

### 1. Health Check
`GET /health/`
Returns system status.
**Response (200 OK):**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "connected"
}
```

### 2. Create Route Plan
`POST /plan/`
Calculates the optimal route and fuel stops.

**Request Body:**
```json
{
  "start": "Chicago, IL",
  "finish": "Dallas, TX",
  "range_miles": 500,
  "mpg": 10.0,
  "start_fuel_gallons": 0.0,
  "station_buffer_miles": 25.0,
  "max_stops": null,
  "currency": "USD",
  "include_route_geometry": true
}
```
*Note: `start` and `finish` accept either string addresses or objects `{"lat": 41.87, "lon": -87.62}`.*

**Success Response (200 OK):**
```json
{
  "plan_id": "550e8400-e29b-41d4-a716-446655440000",
  "start": {
    "query": "Chicago, IL",
    "lat": 41.8781,
    "lon": -87.6298
  },
  "finish": {
    "query": "Dallas, TX",
    "lat": 32.7767,
    "lon": -96.7970
  },
  "route": {
    "distance_miles": 925.4,
    "geometry": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
  },
  "assumptions": {
    "range_miles": 500,
    "mpg": 10.0,
    "start_fuel_gallons": 0.0,
    "station_buffer_miles": 25.0,
    "currency": "USD"
  },
  "stops": [
    {
      "stop_id": 1234,
      "name": "PILOT TRAVEL CENTER #1243",
      "lat": 32.9384,
      "lon": -97.1234,
      "price_usd": 3.15,
      "gallons_purchased": 45.0,
      "cost_usd": 141.75,
      "distance_from_start_miles": 480.2
    }
  ],
  "warnings": [],
  "totals": {
    "fuel_gallons_purchased": 92.5,
    "total_trip_fuel_gallons": 92.5,
    "fuel_cost_usd": 285.45,
    "stop_count": 1
  },
  "cache": {
    "route_cached": false,
    "geocode_cached": true
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid addresses, out of bounds, or unreachable destination.
- `503 Service Unavailable`: OSRM routing provider timeout.

### 3. Retrieve Route Plan
`GET /plan/{plan_id}/`
Retrieves a previously calculated plan from the database cache.

### 4. List Stations
`GET /stations/`
Returns a paginated list of all deduplicated, USA-based fuel stations from the OPIS dataset.

### 5. List Providers
`GET /providers/`
Returns available routing adapters (e.g., `["osrm_public", "osrm_local", "graphhopper"]`).

### 6. OpenAPI Schema & Docs
- `GET /schema/` (drf-spectacular YAML/JSON schema)
- `GET /docs/` (Swagger UI interface)