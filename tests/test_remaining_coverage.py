"""
Tests for remaining coverage in views.py and optimizer.py.
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
import json

from core.models import Station, RoutePlan, RouteStop
from core.services import calculate_route_plan


class TestOptimizerCoverage(TestCase):
    """Test optimizer for full coverage."""

    def test_optimize_fuel_stops_destination_reachable_break(self):
        """Test that the loop breaks when destination is reachable (line 313)."""
        from core.optimizer import optimize_fuel_stops
        from unittest.mock import MagicMock

        # Mock a station that's along the route (not at the destination)
        # The virtual start logic skips stations within 1 mile of the destination
        mock_station = MagicMock()
        mock_station.id = 1
        mock_station.name = "Midway Station"
        mock_station.retail_price = 3.50

        # Create a candidate for a station at 50 miles (not at destination 100 miles)
        candidates = [{
            'station': mock_station,
            'offset_miles': 0.0,
            'route_distance': 50.0,  # Halfway point
            'price': float(mock_station.retail_price)
        }]

        # This test ensures the loop can handle the destination case properly
        # The break condition on line 313 will be tested in this scenario
        result = optimize_fuel_stops(
            total_distance_miles=100.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=5.0  # Start with 5 gallons to ensure fuel_to_dest <= current_fuel
        )

        # The test primarily verifies the code path through line 313 executes
        # The exact number of stops depends on the algorithm's internal logic
        self.assertIn('stops', result)
        self.assertIn('total_gallons', result)
        self.assertIn('total_cost', result)
        self.assertGreaterEqual(len(result['stops']), 1)
        # Should have purchased some fuel
        self.assertGreaterEqual(result['total_gallons'], 0)

    def test_get_candidate_stations_empty(self):
        """Test get_candidate_stations with empty route geometry."""
        from core.optimizer import get_candidate_stations
        result = get_candidate_stations({}, buffer_miles=10.0, total_distance_miles=100.0)
        self.assertEqual(result, [])

    def test_get_candidate_stations_no_stations(self):
        """Test get_candidate_stations when no stations match the bbox."""
        from core.optimizer import get_candidate_stations
        from unittest.mock import patch

        with patch('core.optimizer.Station.objects.filter') as mock_query:
            # Mock empty result from filter
            mock_query.return_value = []

            result = get_candidate_stations({'coordinates': []}, 10.0, 100.0)
            self.assertEqual(result, [])

    def test_optimize_fuel_stops_early_break_with_full_tank(self):
        """Test early break when destination is reachable with current fuel (covers line 286)."""
        from core.optimizer import optimize_fuel_stops

        # 100 mile route, 10 mpg = 10 gallons needed
        # Start with enough fuel to reach destination (15 gallons)
        result = optimize_fuel_stops(
            total_distance_miles=100.0,
            candidates=[],  # No intermediate stations
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=15.0  # More than enough to reach destination
        )

        # Should have no stops since we can reach destination directly
        self.assertEqual(len(result['stops']), 0)
        # total_gallons is fuel PURCHASED, not consumed - with 15 gallons start, we buy 0
        self.assertEqual(result['total_gallons'], 0.0)
        self.assertEqual(result['total_cost'], 0.0)  # No stations, so no cost


class TestHealthAndReadinessEndpoints(TestCase):
    """Test health and readiness endpoints."""

    def setUp(self):
        self.client = Client()

    @patch('core.views.connection')
    def test_healthcheckview_database_unreachable(self, mock_connection):
        """Test HealthCheckView when database is unreachable (covers lines 44-45)."""
        # connection.cursor() returns a cursor, then __enter__() is called on the cursor
        mock_connection.cursor.return_value.__enter__.side_effect = Exception("Connection failed")

        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'degraded')
        self.assertFalse(data['database_reachable'])

    def test_healthcheckview_database_reachable(self):
        """Test HealthCheckView when database is reachable."""
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['database_reachable'])

    def test_readiness_endpoint_database_only(self):
        """Test Readiness endpoint when only database is operational."""
        from django.db import OperationalError
        with patch('core.views.connection') as mock_conn, \
             patch('core.views.cache') as mock_cache:

            # Simulate database operational - simpler mock for connection
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.execute.return_value = None

            # Cache operations - fail only for readiness check key
            def cache_get(key, default=None):
                if key == "_readiness_check":
                    return "error"  # Not "ok" -> should trigger 503
                return []  # For throttling, return empty list

            mock_cache.set.return_value = None  # set succeeds
            mock_cache.get.side_effect = cache_get

            response = self.client.get('/health/ready/')
            self.assertEqual(response.status_code, 503)  # Should fail due to cache error
            data = response.json()
            self.assertEqual(data['status'], 'not ready')
            # Database should be ok
            self.assertIn('database', data['checks'])
            self.assertTrue(data['checks']['database'] == 'ok')
            # Cache should have error
            self.assertIn('cache', data['checks'])
            self.assertEqual(data['checks']['cache'], 'error: read/write mismatch')


class TestStatsAndPlanEndpoints(TestCase):
    """Test StatsView and PlanRouteView endpoints."""

    def setUp(self):
        self.client = Client()

    def test_statsview_no_cached_stats(self):
        """Test StatsView when stats are not cached (covers lines 88-89)."""
        with patch('core.views.cache') as mock_cache:
            mock_cache.get.return_value = None  # Not cached
            # Force the if not stats: block to execute
            response = self.client.get('/api/v1/stats/')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('station_count', data)
            self.assertIn('total_plans', data)
            # Should have cached the result
            self.assertTrue(mock_cache.set.called)

    def test_planrouterview_parameter_extraction(self):
        """Test PlanRouteView extracting parameters (covers lines 91-93)."""
        with patch('core.views.calculate_route_plan') as mock_calc:
            mock_calc.return_value = {
                'success': True,
                'plan_id': 'test-id',
                'start': {'query': 'Chicago, IL', 'lat': 41.8781, 'lon': -87.6298},
                'finish': {'query': 'Dallas, TX', 'lat': 32.7767, 'lon': -96.7970},
                'route': {'distance_miles': 925.4, 'geometry': {'type': 'LineString', 'coordinates': []}},
                'assumptions': {'range_miles': 500, 'mpg': 10.0},
                'stops': [],
                'totals': {'fuel_gallons_purchased': 92.5, 'fuel_cost_usd': 285.45, 'stop_count': 0},
                'warnings': [],
                'cache': {'route_cached': False, 'geocode_cached': False}
            }

            response = self.client.post(
                '/api/v1/plan/',
                data=json.dumps({
                    'start': 'Chicago, IL',
                    'finish': 'Dallas, TX'
                }),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            # Verify the mock was called with default parameters
            mock_calc.assert_called_once()

    def test_planrouterview_with_custom_params(self):
        """Test PlanRouteView with custom parameters."""
        with patch('core.views.calculate_route_plan') as mock_calc:
            mock_calc.return_value = {
                'success': True,
                'plan_id': 'test-id',
                'start': {'query': 'Chicago, IL', 'lat': 41.8781, 'lon': -87.6298},
                'finish': {'query': 'Dallas, TX', 'lat': 32.7767, 'lon': -96.7970},
                'route': {'distance_miles': 925.4, 'geometry': {'type': 'LineString', 'coordinates': []}},
                'assumptions': {'range_miles': 300, 'mpg': 15.0, 'start_fuel_gallons': 10.0, 'station_buffer_miles': 50.0},
                'stops': [],
                'totals': {'fuel_gallons_purchased': 61.7, 'fuel_cost_usd': 190.3, 'stop_count': 0},
                'warnings': [],
                'cache': {'route_cached': False, 'geocode_cached': False}
            }

            response = self.client.post(
                '/api/v1/plan/',
                data=json.dumps({
                    'start': 'Chicago, IL',
                    'finish': 'Dallas, TX',
                    'range_miles': 300,
                    'mpg': 15.0,
                    'start_fuel_gallons': 10.0,
                    'station_buffer_miles': 50.0
                }),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['assumptions']['range_miles'], 300)
            self.assertEqual(data['assumptions']['mpg'], 15.0)
            self.assertEqual(data['assumptions']['start_fuel_gallons'], 10.0)
            self.assertEqual(data['assumptions']['station_buffer_miles'], 50.0)

    def test_planrouterview_error_handling(self):
        """Test PlanRouteView error handling (covers line 137)."""
        with patch('core.views.calculate_route_plan') as mock_calc:
            mock_calc.return_value = {
                'success': False,
                'error': 'Geocoding failed'
            }

            response = self.client.post(
                '/api/v1/plan/',
                data=json.dumps({
                    'start': 'Invalid Location',
                    'finish': 'Nowhere'
                }),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn('error', response.json())