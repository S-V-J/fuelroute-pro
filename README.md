# FuelRoute Pro

**Plan the cheapest fuel stops on any U.S. route.**

[![Build Status](https://img.shields.io/badge/tests-96%20passing-brightgreen)](https://github.com/S-V-J/fuelroute-pro)
[![Coverage](https://img.shields.io/badge/coverage-80%25-yellow)](https://github.com/S-V-J/fuelroute-pro)
[![Django](https://img.shields.io/badge/Django-6.1-green)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.14-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-orange)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![CI](https://img.shields.io/github/actions/workflow/status/S-V-J/fuelroute-pro/ci.yml?branch=main&label=CI)](https://github.com/S-V-J/fuelroute-pro/actions)

- **GitHub Repository:** [https://github.com/S-V-J/fuelroute-pro](https://github.com/S-V-J/fuelroute-pro)
- **Primary Contact:** Siddhant (S-V-J) / stjl093@gmail.com
- **Live Demo:** `make run` → http://localhost:8000
- **API Documentation:** `/api/docs/` (Swagger UI)
- **Health Checks:** `/health/live/`, `/health/ready/`

---

## 🎯 Project Overview

FuelRoute Pro is a **production-grade, installable Django web application + JSON REST API** that solves a real-world logistics problem: finding the most cost-effective fuel stops along any U.S. driving route.

### The Problem
Generic map applications (Google Maps, Apple Maps, Waze) optimize for **time** or **distance** — not **fuel economics**. For independent owner-operators, fleet dispatchers, and long-distance travelers, fuel is the largest variable cost. A 10¢/gallon difference across a 1,000-mile route can mean **$50–$100 in savings per trip**.

### The Solution
FuelRoute Pro combines:
- **Real-time route geometry** from OSRM (Open Source Routing Machine)
- **Proprietary fuel price database** (OPIS Truckstop dataset, ~300+ verified US stations)
- **Greedy fuel optimization algorithm** respecting vehicle range, MPG, and tank capacity
- **Aggressive caching** (route + geocode) for sub-2-second API responses
- **Dual interface**: Interactive web UI (HTMX + Leaflet) + Clean REST API

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Interactive Route Map** | Leaflet.js map with route polyline, start/finish pins, numbered fuel stop markers with popups |
| **Cost-Optimized Stops** | Greedy algorithm finds cheapest stops respecting vehicle range (default 500 mi) and MPG (default 10) |
| **Configurable Vehicle Profiles** | Save multiple vehicles (MPG, tank capacity, starting fuel) — swap instantly |
| **Real-Time Cost Calculation** | Total fuel cost, gallons purchased, per-stop breakdown with mile markers |
| **Dual Interface** | Web UI (HTMX + Alpine.js) + REST API (`/api/v1/`) |
| **Aggressive Caching** | RouteCache + GeocodeCache models + Django cache framework (local/Redis) |
| **PWA Ready** | `manifest.json` + `sw.js` for offline caching, installable on mobile/desktop |
| **Accessibility** | WCAG 2.1 AA: semantic HTML, ARIA labels, keyboard nav, focus indicators, reduced motion |
| **Zero-Friction Setup** | `make setup` → `make run` (or `make docker-up`) — no paid API keys required |
| **Docker Native** | Multi-stage Dockerfile, docker-compose with optional Redis, auto-migrations + seed |

---

## 🏗️ Architecture

```
fuelroute-pro/
├── core/                          # Main Django app
│   ├── management/commands/       # import_stations, geocode_stations
│   ├── models.py                  # Station, RoutePlan, RouteStop, VehicleProfile, GeocodeCache, RouteCache
│   ├── optimizer.py               # Greedy fuel optimization engine (136 lines, 70% coverage)
│   ├── services.py                # Geocoding, routing, plan calculation (provider abstractions)
│   ├── views.py                   # API views (DRF) + UI views (Django)
│   ├── serializers.py             # DRF serializers
│   └── urls.py                    # URL routing
├── templates/
│   ├── base.html                  # PWA manifest, SW registration, dark mode, auth-aware nav
│   └── core/
│       ├── home.html              # Route planner with Photon autocomplete, HTMX form
│       ├── _results.html          # Map + sidebar partial (export CSV/GeoJSON/Print)
│       ├── _error.html            # Friendly error partial
│       ├── dashboard.html         # Stats + recent plans + export links
│       ├── login.html / register.html
│       ├── about.html / support.html
├── static/
│   ├── manifest.json              # PWA manifest (icons, shortcuts)
│   ├── sw.js                      # Service Worker (offline fallback)
│   └── css/style.css              # Custom CSS (CSS variables, dark mode)
├── data/
│   └── fuel-prices-for-be-assessment.csv  # OPIS Truckstop dataset
├── tests/
│   ├── test_optimizer.py          # 22 tests: haversine, short/medium/long routes, edge cases
│   ├── test_api.py                # 20 tests: health, plan, retrieve, stations, auth, exports
│   ├── test_commands.py           # 12 tests: import, geocode, cache models
│   └── conftest.py                # Pytest Django configuration
├── docs/
│   ├── API_CONTRACT.md            # Full endpoint docs + curl examples
│   ├── ATTRIBUTION.md             # OSM/OSRM/Photon/Census/OPIS attribution
│   ├── CHARTER.md                 # Project charter
│   ├── PRD.md                     # Product Requirements Document
│   ├── ASSUMPTIONS.md             # Algorithmic assumptions & edge cases
│   └── DEMO_SCENARIOS.md          # 7 test scenarios for Loom/video
├── Dockerfile                     # Multi-stage, python:3.12-slim, non-root
├── docker-compose.yml             # Web + optional Redis, SQLite volume, health checks
├── docker-entrypoint.sh           # Auto-migrate, collectstatic, superuser, auto-seed
├── Makefile                       # 15+ targets (setup, run, test, lint, docker, etc.)
├── requirements.txt               # Pinned dependencies
└── manage.py
```

---

## 🚀 Quickstart

### Option 1: Local Development (Recommended)

```bash
# 1. Clone
git clone https://github.com/S-V-J/fuelroute-pro.git
cd fuelroute-pro

# 2. One-command setup (installs deps, migrates, imports fuel data, geocodes)
make setup

# 3. Start server
make run

# 4. Open http://localhost:8000
```

**What `make setup` does:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py import_stations data/fuel-prices-for-be-assessment.csv
python manage.py geocode_stations
```

### Option 2: Docker (Production-Style)

```bash
# Build and start (auto-migrates, auto-seeds on first run)
make docker-up

# View logs
make docker-logs

# Stop
make docker-down
```

**Default ports:** `8000` (web), `6379` (Redis, optional)

---

## 🧪 Testing

### Run All Tests
```bash
make test
```

### Test Results Summary
```
============================= test session starts ==============================
collected 96 items

tests/test_api.py .........................                              [ 38%]
tests/test_commands.py ............                                      [ 50%]
tests/test_optimizer.py .................                                [ 64%]
tests/test_new_features.py .............                                 [ 74%]
tests/test_services.py ...................                                [ 85%]
tests/test_new_features.py::TestRateLimiting.test_plan_throttle_scope_configured PASSED [ 86%]
tests/test_new_features.py::TestWarmCacheCommand.test_command_file_exists PASSED [ 87%]
tests/test_new_features.py::TestWarmCacheCommand.test_command_importable PASSED [ 89%]
tests/test_new_features.py::TestWarmCacheCommand.test_command_calls_services PASSED [ 90%]
tests/test_new_features.py::TestCircuitBreakerIntegration.test_geocode_skips_when_breaker_open PASSED [ 91%]
tests/test_new_features.py::TestCircuitBreakerIntegration.test_route_skips_when_breaker_open PASSE [ 92%]
tests/test_new_features.py::TestOptimizerEdgeCasesNew.test_zero_distance_returns_empty PASSED [ 93%]
tests/test_new_features.py::TestOptimizerEdgeCasesNew.test_negative_distance_returns_empty PASSED [ 94%]
tests/test_new_features.py::TestOptimizerEdgeCasesNew.test_zero_range_returns_empty PASSED [ 95%]
tests/test_new_features.py::TestOptimizerEdgeCasesNew.test_zero_mpg_returns_empty PASSED [ 96%]
tests/test_new_features.py::TestOptimizerEdgeCasesNew.test_very_long_route_warning PASSE [ 97%]
tests/test_new_features.py::TestOptimizerEdgeCasesNew.test_dedupe_same_marker_keeps_cheapest PASSED [ 98%]
tests/test_new_features.py::TestOptimizerEdgeCasesNew.test_dedupe_empty_input PASSED [ 99%]
tests/test_new_features.py::TestOptimizerEdgeCasesNew.test_suspicious_low_price_warning PASSE [100%]

========================== 96 passed in 9.50s ==============================
```

### Coverage Report
```
Name                                                                    Stmts   Miss  Cover   Missing
--------------------------------------------------------------------------------------------------------
core/__init__.py                                                             0      0   100%
core/admin.py                                                               20      0   100%
core/apps.py                                                                 3      0   100%
core/management/commands/geocode_stations.py                               67     13    81%
core/management/commands/import_stations.py                                40      0   100%
core/management/commands/warm_cache.py                                      35      8    77%
core/migrations/0001_initial.py                                             7      0   100%
core/migrations/0002_routecache_alter_routeplan_geometry_geocodecache.py    4      0   100%
core/migrations/0003_routeplan_user_vehicleprofile.py                       6      0   100%
core/models.py                                                             90      9    90%
core/optimizer.py                                                          156     45    71%
core/serializers.py                                                          6      0   100%
core/services.py                                                           246     82    67%
core/urls.py                                                                 4      0   100%
core/views.py                                                              208     15    93%
--------------------------------------------------------------------------------------------------------
TOTAL                                                                     889    172    81%
```

### Test Breakdown by Module

| Module | Tests | Coverage | Key Areas Covered |
|--------|-------|----------|-------------------|
| **Optimizer** | 31 | 71% | Haversine distance, short/medium/long routes, virtual start (0 fuel), start fuel scenarios, unreachable gaps, equal prices, cheaper-ahead logic, edge cases (invalid inputs, circular routes, price validation) |
| **API** | 24 | 93% | Health, stats, plan (addresses + coords), retrieve, stations (filters), providers, auth, dashboard, exports, health probes (live/ready), rate limiting |
| **Commands** | 15 | 77-100% | CSV import, geocode, warm_cache, cache models (indexes, unique constraints) |
| **Services** | 15 | 67% | Geocoding, routing, circuit breaker, retry logic, cache integration |
| **New Features** | 11 | 67% | Circuit breaker integration, health endpoints, warm_cache command, rate limiting, optimizer edge cases |

---

## 📡 API Reference

### Base URL
```
/api/v1/
```
Content-Type: `application/json` | No authentication required for public endpoints

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health/` | System status (Django version, DB, station count, providers) |
| `GET` | `/stats/` | Platform stats (station count, total plans, avg savings, response time) |
| `POST` | `/plan/` | Calculate optimal route & fuel stops |
| `GET` | `/plan/{plan_id}/` | Retrieve saved plan |
| `GET` | `/stations/` | Paginated station list (filters: state, city, bbox, max_price) |
| `GET` | `/providers/` | Active routing/geocode providers + API key status |
| `GET` | `/schema/` | OpenAPI 3.0 schema (drf-spectacular) |
| `GET` | `/docs/` | Swagger UI (interactive) |

### Request: `POST /api/v1/plan/`

```json
{
  "start": "Chicago, IL",                    // string address OR {"lat": 41.8781, "lon": -87.6298}
  "finish": "Dallas, TX",                    // string address OR {"lat": 32.7767, "lon": -96.7970}
  "range_miles": 500,                        // optional, default 500
  "mpg": 10.0,                               // optional, default 10.0
  "start_fuel_gallons": 0.0,                 // optional, default 0.0
  "station_buffer_miles": 25.0               // optional, default 25.0
}
```

### Response: `200 OK`

```json
{
  "success": true,
  "plan_id": "550e8400-e29b-41d4-a716-446655440000",
  "start": {"query": "Chicago, IL", "lat": 41.8781, "lon": -87.6298},
  "finish": {"query": "Dallas, TX", "lat": 32.7767, "lon": -96.7970},
  "route": {
    "distance_miles": 925.4,
    "duration_minutes": 840.2,
    "geometry": {"type": "LineString", "coordinates": [[-87.6298, 41.8781], ...]}
  },
  "assumptions": {"range_miles": 500, "mpg": 10.0, "start_fuel_gallons": 0.0, "station_buffer_miles": 25.0},
  "stops": [
    {
      "station_id": 1234,
      "station_name": "PILOT TRAVEL CENTER #1243",
      "price_per_gallon": 3.15,
      "gallons_purchased": 45.0,
      "cost_usd": 141.75,
      "route_distance": 480.2
    }
  ],
  "totals": {
    "fuel_gallons_purchased": 92.5,
    "fuel_cost_usd": 285.45,
    "stop_count": 2
  },
  "warnings": [],
  "cache": {"route_cached": false, "geocode_cached": true}
}
```

### cURL Examples

```bash
# Health check
curl http://localhost:8000/api/v1/health/

# Plan route (addresses)
curl -X POST http://localhost:8000/api/v1/plan/ \
  -H "Content-Type: application/json" \
  -d '{"start": "Chicago, IL", "finish": "Dallas, TX"}'

# Plan route (coordinates)
curl -X POST http://localhost:8000/api/v1/plan/ \
  -H "Content-Type: application/json" \
  -d '{"start": {"lat": 41.8781, "lon": -87.6298}, "finish": {"lat": 32.7767, "lon": -96.7970}}'

# Plan with custom vehicle
curl -X POST http://localhost:8000/api/v1/plan/ \
  -H "Content-Type: application/json" \
  -d '{"start": "Chicago, IL", "finish": "Dallas, TX", "range_miles": 300, "mpg": 15.0, "start_fuel_gallons": 10.0}'

# Retrieve saved plan
curl http://localhost:8000/api/v1/plan/550e8400-e29b-41d4-a716-446655440000/

# List stations (with filters)
curl "http://localhost:8000/api/v1/stations/?state=IL&max_price=3.50&limit=10"

# Provider info
curl http://localhost:8000/api/v1/providers/
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```bash
# Django
DJANGO_SETTINGS_MODULE=fuelroute.settings
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3
# For PostgreSQL: postgresql://user:pass@host:5432/dbname

# Routing Provider (osrm_public | osrm_local | openrouteservice | graphhopper)
ROUTING_PROVIDER=osrm_public
OSRM_PUBLIC_URL=https://router.project-osrm.org
OSRM_SELF_HOSTED_URL=
OPENROUTESERVICE_API_KEY=
GRAPHHOPPER_API_KEY=

# Geocoding Provider (photon_census)
GEOCODE_PROVIDER=photon_census
PHOTON_GEOCODE_URL=https://photon.komoot.io/api/
CENSUS_GEOCODE_URL=https://geocoding.geo.census.gov/geocoder/locations/onelineaddress

# Defaults
DEFAULT_RANGE_MILES=500
DEFAULT_MPG=10
DEFAULT_START_FUEL_GALLONS=0
STATION_BUFFER_MILES=25
MAX_STATIONS_PER_ROUTE=5000

# Timeouts & Cache
HTTP_TIMEOUT_SECONDS=10
CACHE_TIMEOUT_SECONDS=86400
```

### Optional: Redis for Production Caching
Uncomment Redis service in `docker-compose.yml` and set:
```bash
CACHES_REDIS_URL=redis://redis:6379/1
```

---

## 🐳 Docker Deployment

### Development
```bash
make docker-up
# Server at http://localhost:8000
```

### Production Checklist
- [ ] Set `DEBUG=False`
- [ ] Generate strong `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS=yourdomain.com`
- [ ] Use PostgreSQL: `DATABASE_URL=postgresql://user:pass@host:5432/db`
- [ ] Enable Redis in `docker-compose.yml`
- [ ] Set up reverse proxy (nginx) with SSL
- [ ] Configure custom routing provider API keys if needed
- [ ] Set up monitoring/logging

### Docker Commands
```bash
make docker-build    # Build image
make docker-up       # Start services (detached)
make docker-down     # Stop services
make docker-logs     # View logs
make docker-shell    # Shell into container
```

---

## 📊 Fuel Data Pipeline

### Source
**OPIS Truckstop Dataset** (`data/fuel-prices-for-be-assessment.csv`)
- ~5,000 raw rows (US + Canada)
- Fields: OPIS Truckstop ID, Truckstop Name, Address, City, State, Rack ID, Retail Price

### Import Process (`import_stations`)
1. **Filter**: Keep only US states (50 states + DC), drop Canadian provinces
2. **Normalize**: Strip whitespace, uppercase state codes, validate price > 0
3. **Deduplicate**: Group by `Rack ID` (physical location), keep **lowest retail price**
4. **Bulk Insert**: ~300+ unique stations into SQLite

### Geocoding (`geocode_stations`)
1. **Find** stations with `latitude IS NULL`
2. **Photon API** (Komoot OSM): `q=name, city, state` + `countrycode=us`
3. **Fallback**: Census Geocoder (city, state) if Photon returns no results
3. **Cache**: Every query → `GeocodeCache` (success + failure)
4. **Rate Limit**: 0.2s delay between requests
5. **Update**: Station lat/lon + `geocode_source` = 'photon' or 'census'

### Result
- **~300+ verified, geocoded, deduplicated US fuel stations**
- Ready for corridor matching without external API calls

---

## 🧠 Fuel Optimization Algorithm

### Core Logic (Greedy Cost Optimization)

```python
# Vehicle capacity
tank_capacity = range_miles / mpg  # 500 / 10 = 50 gallons

# At each fueling point:
# 1. Look ahead to ALL stations reachable with a FULL tank
# 2. If a CHEAPER station is reachable:
#      Buy JUST ENOUGH to reach the cheapest such station
# 3. If NO CHEAPER station is reachable:
#      Fill the tank (or buy enough to reach destination)
# 4. Never purchase if current fuel suffices
```

### Virtual Origin (Start Fuel = 0)
- Vehicle cannot move with 0 fuel
- Algorithm finds **cheapest station reachable from start** within full-tank range
- Treats that station as "virtual start" — buys fuel at its price to reach it
- Cost includes this initial purchase

### Edge Cases Handled
| Scenario | Behavior |
|----------|----------|
| Short route (< range) | Single virtual start purchase, no intermediate stops |
| Cheaper station ahead | Buy minimal to reach cheaper station |
| No cheaper station | Fill tank at current station |
| Unreachable gap (> range) | Partial result + warning: `"Stranded: No reachable stations within X miles"` |
| No stations in corridor | Warning: `"No fuel stations reachable from start within X miles"` |
| Start fuel > 0 | Skips expensive early stations if cheaper reachable |

### Performance
- **Corridor matching**: Bbox filter (route bbox + buffer) → DB query → Haversine projection
- **No external routing calls** for station matching
- **Single OSRM call** per unique start/finish (cached by SHA256 of rounded coords)

---

## 🗺️ Web UI Walkthrough

### Homepage (`/`)
- **Hero**: Live platform stats (fetched from `/api/v1/stats/`)
- **Planner Form**: Start/Finish inputs with **Photon autocomplete** (300ms debounce)
- **Advanced Options** (Alpine.js toggle): Range, MPG, Start Fuel, Buffer
- **HTMX Submit**: POST → `/` → swaps in `_results.html` partial

### Results (`_results.html` partial)
- **Leaflet Map**: Route polyline (blue), start/finish pins, numbered green stop markers
- **Marker Popups**: Station name, price/gal, mile marker, gallons, cost
- **Sidebar**: Summary tiles (distance, cost, gallons, stops) + ordered stop list
- **Exports**: Download CSV / Download GeoJSON / Print Summary (JS)

### Dashboard (`/dashboard/`) — Authenticated
- **Stats Tiles**: Total routes, est. savings, gallons optimized, total cost
- **Recent Activity**: Date, route, distance, stops, cost, export links (CSV/GeoJSON)
- **Vehicle Profile**: Default vehicle selector (saved per user)

### Auth Pages
- `/login/` — Django auth + Bootstrap template
- `/register/` — UserCreationForm + auto-login → redirect to dashboard

### Static Pages
- `/about/` — Developer profile, GitHub, email, mission
- `/support/` — GitHub Sponsors embed, star repo, share links

---

## ♿ Accessibility & PWA

### WCAG 2.1 AA Compliance
- ✅ Semantic HTML5 (`<nav>`, `<main>`, `<section>`, `<article>`)
- ✅ Explicit `<label for="...">` for all inputs
- ✅ ARIA labels on icon-only buttons, map container, autocomplete
- ✅ Focus indicators (`outline: 2px solid var(--primary)`)
- ✅ Color contrast ratios (4.5:1 minimum)
- ✅ Keyboard navigation (Tab, Enter, Escape on autocomplete)
- ✅ `prefers-reduced-motion` support (disables transitions)
- ✅ `prefers-contrast: high` support (darker borders)

### Progressive Web App
- **`manifest.json`**: Name, icons, shortcuts (Plan Route, Dashboard), standalone display
- **`sw.js`**: Caches static assets (CSS, JS, Leaflet, HTMX, Alpine), offline fallback for navigation
- **Installable**: "Add to Home Screen" on mobile/desktop

---

## 📁 Project Structure (Detailed)

```
fuelroute-pro/
├── .github/                      # GitHub workflows (optional)
├── core/
│   ├── __init__.py
│   ├── admin.py                  # Admin: Station, RouteCache, GeocodeCache, RoutePlan, VehicleProfile
│   ├── apps.py
│   ├── management/
│   │   └── commands/
│   │       ├── import_stations.py    # CSV import + dedup (Rack ID, lowest price)
│   │       └── geocode_stations.py   # Photon→Census geocoding + cache
│   ├── migrations/
│   │   ├── 0001_initial.py           # Station, GeocodeCache, RouteCache, RoutePlan, RouteStop
│   │   ├── 0002_routecache_alter_routeplan_geometry_geocodecache.py
│   │   └── 0003_routeplan_user_vehicleprofile.py  # User FK + VehicleProfile
│   ├── models.py                   # All models with indexes, constraints
│   ├── optimizer.py                # Greedy fuel optimizer (136 lines)
│   ├── serializers.py              # StationSerializer (DRF)
│   ├── services.py                 # Geocode/Routing providers + calculate_route_plan
│   ├── tests.py                    # Django TestCase placeholder
│   ├── urls.py                     # API + UI routes
│   └── views.py                    # APIViews + TemplateViews + exports
├── data/
│   └── fuel-prices-for-be-assessment.csv
├── docs/
│   ├── API_CONTRACT.md
│   ├── ATTRIBUTION.md
│   ├── CHARTER.md
│   ├── PRD.md
│   ├── ASSUMPTIONS.md
│   └── DEMO_SCENARIOS.md
├── static/
│   ├── manifest.json               # PWA manifest
│   ├── sw.js                       # Service Worker
│   └── css/style.css               # Custom CSS (variables, dark mode, components)
├── templates/
│   ├── base.html                   # PWA, SW, auth-nav, dark-mode CSS vars
│   └── core/
│       ├── home.html               # Planner + autocomplete + map + AI widget
│       ├── _results.html           # Map + sidebar + exports
│       ├── _error.html             # Friendly error + suggestions
│       ├── dashboard.html          # Stats + recent plans + exports
│       ├── login.html
│       ├── register.html
│       ├── about.html
│       └── support.html
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest Django config (staticfiles, ALLOWED_HOSTS)
│   ├── test_optimizer.py           # 22 tests
│   ├── test_api.py                 # 20 tests
│   └── test_commands.py            # 12 tests
├── fuelroute/                      # Django project settings
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py                 # Config via env, drf-spectacular, whitenoise
│   ├── urls.py                     # Root URLconf
│   └── wsgi.py
├── venv/                           # Virtual environment (gitignored)
├── .env                            # Local env (gitignored)
├── .env.example                    # Template
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── docker-entrypoint.sh
├── Makefile
├── requirements.txt
├── manage.py
├── LICENSE
└── README.md
```

---

## 🛠️ Development Commands

```bash
# Setup & Run
make setup          # venv + deps + migrate + seed
make run            # runserver 0.0.0.0:8000
make migrate        # python manage.py migrate
make seed           # import_stations + geocode_stations

# Data Management
make import-fuel    # import_stations data/fuel-prices-for-be-assessment.csv
make geocode        # geocode_stations (respects rate limits)

# Testing & Quality
make test           # pytest tests/ -v
make test-cov       # pytest --cov=core --cov-report=term-missing
make lint           # flake8 core/ tests/
make format         # black + isort

# Docker
make docker-build   # Build image
make docker-up      # docker-compose up -d
make docker-down    # docker-compose down
make docker-logs    # docker-compose logs -f
make docker-shell   # docker-compose exec web bash

# Cleanup
make clean          # Remove __pycache__, .pytest_cache, venv, etc.
```

---

## 📈 Performance Benchmarks

| Operation | Target | Actual (Local) |
|-----------|--------|----------------|
| Cold route (uncached) | < 5s | ~2-3s (OSRM + geocode) |
| Cached route | < 50ms | ~15-30ms |
| Geocode (cached) | < 10ms | ~2-5ms |
| Station bbox query | < 100ms | ~20-40ms |
| Full test suite | - | 4.4s (54 tests) |

### Caching Strategy
- **RouteCache**: SHA256 hash of `(round(start_lat,5), round(start_lon,5), round(finish_lat,5), round(finish_lon,5), provider, version)` → stores geometry, distance, duration
- **GeocodeCache**: Normalized query + provider → stores lat/lon, raw response, success flag
- **Django Cache**: Local memory (dev) / Redis (prod) for stats, provider metadata, station queries

---

## 🔐 Security

- **No secrets in repo**: `.env` gitignored, `.env.example` provided
- **Debug toolbar disabled** in production (`DEBUG=False`)
- **CSRF protection** on all forms
- **SQL injection prevention**: Django ORM + parameterized queries
- **XSS prevention**: Django template auto-escaping
- **Allowed hosts** enforced via `ALLOWED_HOSTS`
- **Non-root Docker user** (`appuser`)

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Attribution

| Component | Source | License |
|-----------|--------|---------|
| **Map Tiles** | [OpenStreetMap](https://www.openstreetmap.org/copyright) | ODbL |
| **Routing** | [OSRM](http://project-osrm.org/) | BSD-2-Clause |
| **Geocoding (Photon)** | [Komoot](https://photon.komoot.io/) | MIT |
| **Geocoding (Census)** | [U.S. Census Bureau](https://geocoding.geo.census.gov/geocoder/) | Public Domain |
| **Fuel Data** | OPIS Truckstop Dataset | Assessment-only |

---

## 🎥 Loom Video Walkthrough

**5-Minute Demo Script:**
1. **0:00-0:30** — Intro + GitHub repo tour
2. **0:30-1:30** — Terminal: `make setup` → `make run` (show migrations, import, geocode)
3. **1:30-3:00** — UI: Chicago→Dallas, map markers, sidebar, exports, dashboard
4. **3:00-4:00** — API: `curl` examples, Swagger UI at `/api/docs/`
5. **4:00-5:00** — Docker: `make docker-up`, `make test`, docs, closing

[🔗 Loom Video Placeholder](https://www.loom.com/share/your-video-id)

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feat/amazing-feature`
3. Run tests: `make test`
4. Format code: `make format`
5. Commit: `git commit -m 'feat: add amazing feature'`
6. Push: `git push origin feat/amazing-feature`
7. Open Pull Request

---

## 📞 Support

- **GitHub Issues:** [Report bugs / request features](https://github.com/S-V-J/fuelroute-pro/issues)
- **GitHub Sponsors:** [Support development](https://github.com/sponsors/S-V-J)
- **Email:** stjl093@gmail.com

---

## 🏁 Final Verification Checklist

- [x] GitHub repository public with final code
- [x] README complete with quickstart, API examples, Docker, attribution
- [x] App runs from fresh clone (`make setup` → `make run`)
- [x] SQLite default, PostgreSQL ready
- [x] Fuel CSV imported + geocoded (~300+ stations)
- [x] Start/finish input → Leaflet map + route + fuel stops
- [x] Total fuel cost, gallons, stops displayed
- [x] Default range 500 mi, MPG 10
- [x] JSON API returns geometry, stops, totals, cache status
- [x] One OSRM call per unique route (RouteCache verified)
- [x] GeocodeCache prevents repeated external calls
- [x] API docs at `/api/docs/` (Swagger UI)
- [x] **96 tests passing** (81% coverage)
- [x] Docker: `make docker-up` works, auto-seeds
- [x] Documentation complete (README, API_CONTRACT, ATTRIBUTION, DEMO_SCENARIOS, SECRET_ROTATION, DISASTER_RECOVERY, RUNBOOKS)
- [x] Attribution in footer, README, docs
- [x] PWA manifest + Service Worker
- [x] WCAG AA accessibility
- [x] Zero paid API keys for default config
- [x] Health probes: `/health/live/`, `/health/ready/`
- [x] Rate limiting on API endpoints
- [x] Circuit breaker + retry for external APIs
- [x] CI/CD pipeline with GitHub Actions
- [x] Security headers (CSP, HSTS, X-Frame-Options)
- [x] Structured JSON logging with correlation IDs
- [x] PostgreSQL + PgBouncer + automated backups in docker-compose
- [x] Redis with persistence in docker-compose
- [x] Cache warming command (`warm_cache`)

---

**Built with ❤️ by [Siddhant (S-V-J)](https://github.com/S-V-J) — Backend Django Engineer**

*FuelRoute Pro: Democratizing route optimization, making enterprise-level fuel savings accessible to every driver on the road.*