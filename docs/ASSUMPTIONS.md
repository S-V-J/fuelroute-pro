# FuelRoute Pro — Algorithmic Assumptions & Edge Cases

## 1. Virtual Origin Fueling Logic
If `start_fuel_gallons` is set to `0` (the default), the vehicle cannot mathematically move. To solve this, the optimizer identifies the 5 closest stations to the start coordinate and assumes the driver fuels up at the **cheapest** of these 5 stations to initialize the journey. This virtual first stop is added to the itinerary and total cost.

## 2. OPIS Dataset Deduplication
The raw OPIS CSV contains multiple rows for the same physical location (e.g., different rack IDs, branded vs. unbranded, or slight coordinate variations). 
- **Rule**: During the database import phase, stations are grouped by `Rack ID` or spatial proximity (< 0.1 miles). 
- **Resolution**: The system retains only the row with the **lowest `Retail Price`** for that physical location.

## 3. Spatial Corridor Filtering
Calculating distances to all 5,000+ stations for every request is computationally expensive.
- **Rule**: The system generates a bounding polygon around the OSRM route geometry using the `station_buffer_miles` (default 25 miles).
- **Resolution**: Only stations falling within this bounding box are loaded into memory for the optimization algorithm.

## 4. Detour Cost Approximation
For the MVP, the system does not make secondary routing API calls to calculate the exact driveway entrance/exit distances for every truck stop.
- **Rule**: The distance to a station is calculated as the distance along the primary route to the nearest geometric node, plus the **Haversine (straight-line) distance** from that node to the station's coordinates.

## 5. Geopolitical Filtering (USA Focus)
The OPIS dataset includes Canadian provinces (e.g., AB, ON, BC) with prices in CAD.
- **Rule**: Any station where the `State` column matches a Canadian province code is strictly dropped during the `manage.py import_stations` command. The product is exclusively USA-focused for MVP.

## 6. Currency Standardization
All prices in the OPIS dataset are assumed to be **USD per gallon**. No currency conversion is applied.

## 7. Edge Case Handling
- **No Route Exists**: If OSRM cannot find a driving path (e.g., start/finish separated by an ocean or unmapped terrain), return HTTP 400 with `{"error": "No drivable route found between coordinates."}`.
- **No Reachable Stops**: If the route passes through a "fuel desert" where no stations exist within the buffer, return a partial result with a warning: `{"warnings": ["Insufficient fuel stations found for leg between Mile 200 and Mile 600."]}`.
- **Missing Coordinates**: If a station in the CSV lacks valid Lat/Lon data, it is silently dropped during import.
- **Rate Limiting**: If the OSRM public demo server returns HTTP 429 (Too Many Requests), the system will fallback to a cached straight-line approximation and flag `route_cached: false, degraded_mode: true` in the response.