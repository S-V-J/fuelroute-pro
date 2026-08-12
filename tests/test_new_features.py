"""
Tests for new production hardening features:
- Circuit breaker resilience in services.py
- Health endpoints (liveness, readiness)
- warm_cache management command
- Rate limiting on API endpoints
- Optimizer edge cases (invalid inputs, circular routes, price validation)
"""
import pytest
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from unittest.mock import patch, MagicMock
from django.core.cache import cache
import time

from core.services import CircuitBreaker, geocode_location, get_driving_route
from core.optimizer import optimize_fuel_stops, _dedupe_same_marker
from core.models import Station


# ---------------------------------------------------------------------------
# Circuit Breaker Tests
# ---------------------------------------------------------------------------
class TestCircuitBreaker(TestCase):
    def setUp(self):
        self.cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

    def test_initial_state_allows_requests(self):
        self.assertTrue(self.cb.allow_request())

    def test_opens_after_threshold_failures(self):
        for _ in range(3):
            self.cb.record_failure()
        self.assertFalse(self.cb.allow_request())

    def test_records_success_resets_failures(self):
        self.cb.record_failure()
        self.cb.record_failure()
        self.assertEqual(self.cb.failures, 2)
        self.cb.record_success()
        self.assertEqual(self.cb.failures, 0)
        self.assertFalse(self.cb.open)

    def test_auto_recovers_after_timeout(self):
        for _ in range(3):
            self.cb.record_failure()
        self.assertFalse(self.cb.allow_request())
        time.sleep(1.1)
        self.assertTrue(self.cb.allow_request())


# ---------------------------------------------------------------------------
# Optimizer Edge Case Tests
# ---------------------------------------------------------------------------
class TestOptimizerEdgeCasesNew(TestCase):
    def _make_candidate(self, station_id, route_distance, price, lat=40.0, lon=-75.0):
        class FakeStation:
            id = station_id
            name = f"Station {station_id}"
            retail_price = price
            latitude = lat
            longitude = lon
            state = "PA"
        return {
            'station': FakeStation(),
            'offset_miles': 1.0,
            'route_distance': route_distance,
            'price': price,
        }

    def test_zero_distance_returns_empty(self):
        result = optimize_fuel_stops(
            total_distance_miles=0,
            candidates=[],
            range_miles=500,
            mpg=10,
            start_fuel_gallons=0,
        )
        self.assertEqual(result['stops'], [])
        self.assertIn('positive', result['warnings'][0])

    def test_negative_distance_returns_empty(self):
        result = optimize_fuel_stops(
            total_distance_miles=-10,
            candidates=[],
            range_miles=500,
            mpg=10,
            start_fuel_gallons=0,
        )
        self.assertEqual(result['stops'], [])
        self.assertIn('positive', result['warnings'][0])

    def test_zero_range_returns_empty(self):
        result = optimize_fuel_stops(
            total_distance_miles=100,
            candidates=[],
            range_miles=0,
            mpg=10,
            start_fuel_gallons=0,
        )
        self.assertEqual(result['stops'], [])
        self.assertIn('range', result['warnings'][0])

    def test_zero_mpg_returns_empty(self):
        result = optimize_fuel_stops(
            total_distance_miles=100,
            candidates=[],
            range_miles=500,
            mpg=0,
            start_fuel_gallons=0,
        )
        self.assertEqual(result['stops'], [])
        self.assertIn('MPG', result['warnings'][0])

    def test_very_long_route_warning(self):
        candidates = [self._make_candidate(1, 100, 3.0)]
        result = optimize_fuel_stops(
            total_distance_miles=3500,
            candidates=candidates,
            range_miles=500,
            mpg=10,
            start_fuel_gallons=0,
        )
        self.assertTrue(
            any('exceeds expected US max' in w for w in result['warnings']),
            f"Expected circular-route warning, got: {result['warnings']}"
        )

    def test_dedupe_same_marker_keeps_cheapest(self):
        c1 = {'station': None, 'route_distance': 100.0, 'price': 3.50, 'offset_miles': 1.0}
        c2 = {'station': None, 'route_distance': 100.3, 'price': 3.00, 'offset_miles': 0.8}
        c3 = {'station': None, 'route_distance': 200.0, 'price': 4.00, 'offset_miles': 1.2}
        deduped = _dedupe_same_marker([c1, c2, c3], tolerance=0.5)
        prices = [c['price'] for c in deduped]
        self.assertIn(3.00, prices)
        self.assertNotIn(3.50, prices)
        self.assertEqual(len(deduped), 2)

    def test_dedupe_empty_input(self):
        self.assertEqual(_dedupe_same_marker([]), [])

    def test_suspicious_low_price_warning(self):
        candidates = [self._make_candidate(1, 100, 0.50)]
        result = optimize_fuel_stops(
            total_distance_miles=200,
            candidates=candidates,
            range_miles=500,
            mpg=10,
            start_fuel_gallons=0,
        )
        self.assertTrue(
            any('suspiciously low' in w for w in result['warnings']),
            f"Expected low price warning, got: {result['warnings']}"
        )


# ---------------------------------------------------------------------------
# Health Endpoint Tests
# ---------------------------------------------------------------------------
class TestHealthEndpoints(TestCase):
    def setUp(self):
        self.client = Client()

    def test_live_endpoint(self):
        response = self.client.get('/health/live/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'alive')

    def test_ready_endpoint_success(self):
        response = self.client.get('/health/ready/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ready')

    def test_ready_checks_database(self):
        response = self.client.get('/health/ready/')
        data = response.json()
        self.assertIn('checks', data)
        self.assertIn('database', data['checks'])
        self.assertEqual(data['checks']['database'], 'ok')

    def test_ready_checks_cache(self):
        response = self.client.get('/health/ready/')
        data = response.json()
        self.assertIn('cache', data['checks'])


# ---------------------------------------------------------------------------
# Rate Limiting Tests
# ---------------------------------------------------------------------------
class TestRateLimiting(TestCase):
    def setUp(self):
        self.client = Client()

    def test_plan_throttle_scope_configured(self):
        from django.conf import settings as django_settings
        throttle_rates = django_settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        self.assertIn('plan', throttle_rates)
        self.assertIn('anon', throttle_rates)


# ---------------------------------------------------------------------------
# Warm Cache Command Tests
# ---------------------------------------------------------------------------
class TestWarmCacheCommand(TestCase):
    def test_command_file_exists(self):
        import os
        path = '/home/ML/spotter-assessment/backend-django/fuelroute-pro/core/management/commands/warm_cache.py'
        self.assertTrue(os.path.exists(path))

    def test_command_importable(self):
        from core.management.commands import warm_cache as wc_module
        import inspect
        source = inspect.getsource(wc_module.Command)
        self.assertIn('warm', source.lower())

    @patch('core.services.geocode_location')
    @patch('core.services.get_driving_route')
    def test_command_calls_services(self, mock_route, mock_geo):
        from django.core.management import call_command
        from io import StringIO
        mock_geo.return_value = {'success': True, 'lat': 40.0, 'lon': -75.0, 'cached': False}
        mock_route.return_value = {'success': True, 'distance_miles': 100.0, 'cached': True}
        out = StringIO()
        call_command('warm_cache', stdout=out)
        self.assertTrue(mock_geo.called)
        self.assertTrue(mock_route.called)


# ---------------------------------------------------------------------------
# Circuit Breaker Integration Tests (services)
# ---------------------------------------------------------------------------
class TestCircuitBreakerIntegration(TestCase):
    @patch('core.services.PHOTON_CIRCUIT_BREAKER')
    @patch('core.services.GeocodeCache.objects.filter')
    def test_geocode_skips_when_breaker_open(self, mock_filter, mock_cb):
        mock_cb.allow_request.return_value = False
        mock_filter.return_value.first.return_value = None
        with patch('core.services._geocode_fallback_census') as mock_fallback:
            mock_fallback.return_value = {'success': False, 'error': 'Location not found'}
            result = geocode_location('Chicago, IL')
            mock_cb.allow_request.assert_called_once()
            mock_fallback.assert_called_once()

    @patch('core.services.OSRM_CIRCUIT_BREAKER')
    @patch('core.services.RouteCache.objects.filter')
    def test_route_skips_when_breaker_open(self, mock_filter, mock_cb):
        mock_cb.allow_request.return_value = False
        mock_filter.return_value.first.return_value = None
        result = get_driving_route(41.8781, -87.6298, 32.7767, -96.7970)
        mock_cb.allow_request.assert_called_once()
        self.assertFalse(result['success'])
        self.assertIn('circuit breaker', result['error'])
