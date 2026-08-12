# FuelRoute Pro — Product Requirements Document (PRD)

## 1. User Personas
- **The Independent Owner-Operator (Dave)**: Pays for his own fuel. Highly sensitive to price-per-gallon variations. Uses the mobile Web UI during breaks to plan his next day's drive.
- **The Fleet Dispatcher (Sarah)**: Manages 50+ trucks. Uses the JSON API to integrate FuelRoute Pro into her internal Transportation Management System (TMS) to enforce cost-saving routes.
- **The 3rd Party Developer (Alex)**: Building a logistics SaaS. Relies on the OpenAPI schema and clean REST endpoints to build a wrapper application.

## 2. User Journeys
### Primary Journey (Interactive Web UI)
1. User lands on the homepage.
2. User enters start ("Chicago, IL") and finish ("Dallas, TX") locations.
3. User leaves default vehicle assumptions (500 mi range, 10 MPG, 0 gal start fuel).
4. User clicks "Calculate Route".
5. System displays an interactive Leaflet map with the OSRM driving route.
6. System displays a sidebar with recommended fuel stops, total cost, and leg distances.
7. User clicks a map marker to view specific station details (brand, price, address).

### Secondary Journey (API Integration)
1. Developer sends a `POST` request to `/api/v1/plan/` with start/finish coordinates and custom vehicle constraints.
2. System returns a JSON payload containing the encoded polyline geometry, optimized stops, and cost breakdown.
3. Developer renders the data on their proprietary frontend.

## 3. Functional Requirements
- **FR1**: Geocode string addresses into latitude/longitude coordinates.
- **FR2**: Fetch driving route geometry and total distance from the OSRM routing provider.
- **FR3**: Filter the static OPIS fuel dataset to a spatial corridor around the route.
- **FR4**: Execute a fuel optimization algorithm that respects vehicle range, MPG, and fuel capacity.
- **FR5**: Render the route and stops on an interactive map via the Web UI.
- **FR6**: Expose all core functionality via a versioned JSON REST API.

## 4. Non-Functional Requirements
- **NFR1 (Performance)**: API responses must return in < 2 seconds for cached routes, and < 5 seconds for uncached routes.
- **NFR2 (Responsiveness)**: Web UI must be 100% mobile-responsive (mobile-first design).
- **NFR3 (Accessibility)**: Web UI must adhere to WCAG 2.1 AA standards (semantic HTML, ARIA labels, keyboard navigation).
- **NFR4 (Portability)**: The application must run out-of-the-box using SQLite without requiring external database setup.

## 5. Error States & Handling
- **Invalid Address**: Geocoding fails. Return HTTP 400 with a user-friendly message ("Could not find location: X").
- **Out of Bounds**: Start/Finish outside the USA. Return HTTP 400 ("Routing is currently restricted to the contiguous United States").
- **Unreachable Destination**: Route distance exceeds vehicle range and no stations exist to bridge the gap. Return HTTP 400 with a warning ("Vehicle range insufficient to reach destination").
- **Routing Timeout**: OSRM public demo fails to respond. Return HTTP 503 ("Routing service temporarily unavailable. Please try again.").

## 6. Performance Goals
- Aggressively cache OSRM route geometries using quantized coordinate hashes.
- Aggressively cache geocoding results to prevent Nominatim rate-limiting.
- Pre-filter and index the OPIS dataset in SQLite using spatial indexing (or rapid bounding-box math) to avoid full-table scans during optimization.

## 7. Data Limitations
- The OPIS dataset is static. Prices do not reflect real-time daily market fluctuations.
- The OPIS dataset contains duplicate entries for the same physical station.
- The OPIS dataset includes Canadian stations, which must be strictly excluded.

## 8. Future Roadmap (Out of Scope for MVP)
- Real-time fuel price API integrations (e.g., OPIS live feed).
- User accounts, authentication, and saved route history.
- Historical price tracking and predictive fuel cost modeling.
- Electric Vehicle (EV) charging station routing and battery degradation modeling.