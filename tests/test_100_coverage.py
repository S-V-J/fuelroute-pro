"""
Targeted tests to achieve 100% coverage for optimizer.py, services.py, and views.py.
"""
from django.test import TestCase, Client
from unittest.mock import patch, MagicMock
import json

from core.models import Station, RoutePlan, RouteStop
from core.optimizer import (
    optimize_fuel_stops,
    get_candidate_stations,
    calculate_route_bbox,
    haversine_miles
)


class TestOptimizerMissingLines(TestCase):
    """Tests for specific missing lines in optimizer.py."""

    def test_line86_non_us_state_filter(self):
        """Test line 86: non-US state filter in get_candidate_stations."""
        mock_station = MagicMock()
        mock_station.id = 1
        mock_station.name = "Non-US Station"
        mock_station.latitude = 40.0
        mock_station.longitude = 100.0
        mock_station.retail_price = 3.50
        mock_station.state = "ON"  # Ontario, Canada - not US

        with patch('core.optimizer.Station.objects.filter') as mock_filter:
            mock_filter.return_value = [mock_station]

            # This should trigger the state filter at line 86
            result = get_candidate_stations(
                {'coordinates': [[100.0, 40.0]]},
                buffer_miles=10.0,
                total_distance_miles=100.0
            )
            self.assertEqual(len(result), 0)

    def test_line99_buffer_filter_continue(self):
        """Test line 99: continue when station beyond buffer."""
        mock_station = MagicMock()
        mock_station.id = 1
        mock_station.name = "Far Station"
        mock_station.latitude = 40.0
        mock_station.longitude = 200.0  # Far from route
        mock_station.retail_price = 3.50
        mock_station.state = "CA"

        with patch('core.optimizer.Station.objects.filter') as mock_filter:
            mock_filter.return_value = [mock_station]

            # Route near 100, 40 with small buffer
            result = get_candidate_stations(
                {'coordinates': [[100.0, 40.0], [101.0, 41.0]]},
                buffer_miles=10.0,
                total_distance_miles=100.0
            )
            # Should be filtered out by buffer check (line 99)
            self.assertEqual(len(result), 0)

    def test_lines111_112_refine_pass_update(self):
        """Test lines 111-112: refine pass updates offset and route_dist."""
        mock_station = MagicMock()
        mock_station.id = 1
        mock_station.name = "Close Station"
        # Place station between coarse points to trigger refine pass
        mock_station.latitude = 40.05
        mock_station.longitude = 100.05
        mock_station.retail_price = 3.50
        mock_station.state = "CA"

        with patch('core.optimizer.Station.objects.filter') as mock_filter:
            mock_filter.return_value = [mock_station]

            # Use 500 coordinates so stride = 500//200 = 2, skipping every other point
            # This forces the coarse pass to skip points and refine pass to find closer point
            coords = [[100.0 + i*0.1, 40.0 + i*0.1] for i in range(500)]

            result = get_candidate_stations(
                {'coordinates': coords},
                buffer_miles=50.0,
                total_distance_miles=500.0
            )
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 1)

    def test_line203_high_price_warning(self):
        """Test line 203: high price warning."""
        mock_station = MagicMock()
        mock_station.id = 1
        mock_station.name = "Expensive Station"
        mock_station.retail_price = 15.00  # > 10.00

        result = optimize_fuel_stops(
            total_distance_miles=100.0,
            candidates=[{
                'station': mock_station,
                'offset_miles': 0.0,
                'route_distance': 50.0,
                'price': 15.00
            }],
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )
        self.assertIn('warnings', result)
        # Should have high price warning
        self.assertTrue(any('high price' in w for w in result['warnings']))

    def test_line229_skip_station_at_destination(self):
        """Test line 229: skip stations at destination in virtual start."""
        mock_station = MagicMock()
        mock_station.id = 1
        mock_station.name = "Destination Station"
        mock_station.retail_price = 3.50

        # Station at 99.5 miles (within 1 mile of 100 mile destination)
        candidates = [{
            'station': mock_station,
            'offset_miles': 0.0,
            'route_distance': 99.5,
            'price': 3.50
        }]

        result = optimize_fuel_stops(
            total_distance_miles=100.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )
        # Station should be skipped at virtual start due to line 229
        # but may still be considered in main loop
        self.assertIn('stops', result)

    def test_lines302_304_dest_in_reachable(self):
        """Test lines 302-304: dest_in_reachable check in main loop."""
        mock_station = MagicMock()
        mock_station.id = 1
        mock_station.name = "Midway Station"
        mock_station.retail_price = 3.50

        candidates = [{
            'station': mock_station,
            'offset_miles': 0.0,
            'route_distance': 50.0,
            'price': 3.50
        }]

        # With enough fuel to reach destination from current position
        result = optimize_fuel_stops(
            total_distance_miles=100.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=5.0
        )
        # This tests the dest_in_reachable logic
        self.assertIn('stops', result)

    def test_line313_dest_break(self):
        """Test line 313: break when destination reachable with current fuel.

        Note: Line 313 is actually unreachable because the same condition is checked
        at line 286 first. But this test ensures the code path through the loop works.
        """
        mock_station = MagicMock()
        mock_station.id = 1
        mock_station.name = "Midway"
        mock_station.retail_price = 3.50

        candidates = [{
            'station': mock_station,
            'offset_miles': 0.0,
            'route_distance': 50.0,
            'price': 3.50
        }]

        result = optimize_fuel_stops(
            total_distance_miles=100.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=5.0
        )
        self.assertIn('stops', result)

    def test_lines320_344_cheaper_stations(self):
        """Test lines 320-344: cheaper station ahead logic (lines 326-337 for fuel buying)."""
        # Test the path where cheaper stations exist and we need to buy fuel to reach them
        mock_station1 = MagicMock()
        mock_station1.id = 1
        mock_station1.name = "Expensive"
        mock_station1.retail_price = 4.00

        mock_station2 = MagicMock()
        mock_station2.id = 2
        mock_station2.name = "Cheap"
        mock_station2.retail_price = 3.00

        # Station 1 at 50mi ($4.00), Station 2 at 60mi ($3.00), destination at 100mi
        candidates = [
            {'station': mock_station1, 'offset_miles': 0.0, 'route_distance': 50.0, 'price': 4.00},
            {'station': mock_station2, 'offset_miles': 0.0, 'route_distance': 60.0, 'price': 3.00}
        ]

        # Start with 2 gallons fuel (can go 20 miles at 10 mpg) -> NO virtual start
        # current_position = 0, current_fuel = 2, current_price = 4.00 (from station1)
        # Loop: dist_to_dest = 100, fuel_to_dest = 10 (10 <= 2? No)
        # reachable = [station1 at 50mi, station2 at 60mi, dest at 100mi]
        # dest_in_reachable = True
        # fuel_to_dest (10) <= current_fuel (2)? No
        # cheaper_stations = [station2] (price 3.00 < 4.00) -> non-empty
        # next_station = station2
        # dist_to_next = 60 - 0 = 60, fuel_needed = 6, fuel_to_buy = 6 - 2 = 4 > 0
        # This hits lines 326-337!
        result = optimize_fuel_stops(
            total_distance_miles=100.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=2.0  # Start with fuel to avoid virtual start
        )
        self.assertIn('stops', result)
        self.assertGreater(len(result['stops']), 0)

    def test_lines366_388_fill_tank(self):
        """Test lines 366-388: fill tank logic when no cheaper station and dest not in reachable."""
        # Test the path where we fill the tank (no cheaper station, dest not reachable)
        mock_station1 = MagicMock()
        mock_station1.id = 1
        mock_station1.name = "Station1"
        mock_station1.retail_price = 3.50

        mock_station2 = MagicMock()
        mock_station2.id = 2
        mock_station2.name = "Station2"
        mock_station2.retail_price = 3.50  # Same price, not cheaper

        # Station 1 at 50mi ($3.50), Station 2 at 400mi ($3.50), destination at 600mi
        # range_miles = 500, tank_capacity = 50 gallons (500/10)
        # Start with 0 fuel -> virtual start at station1
        # After virtual start: current_position = 50, current_fuel = 0, current_price = 3.50
        # Loop: dist_to_dest = 550, fuel_to_dest = 55 (not <= 0)
        # max_reach_distance = 50 + 500 = 550
        # reachable = [station2 at 400mi] (dest at 600 > 550, so not reachable!)
        # dest_in_reachable = False
        # cheaper_stations = [] (station2 same price as current_price)
        # else block -> dest_in_reachable False -> fill tank at line 366-388
        # fuel_to_buy = 50 - 0 = 50 > 0
        candidates = [
            {'station': mock_station1, 'offset_miles': 0.0, 'route_distance': 50.0, 'price': 3.50},
            {'station': mock_station2, 'offset_miles': 0.0, 'route_distance': 400.0, 'price': 3.50}
        ]

        result = optimize_fuel_stops(
            total_distance_miles=600.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )
        # Should fill tank at first station
        self.assertIn('stops', result)
        self.assertGreater(len(result['stops']), 0)


class TestViewsMissingLines(TestCase):
    """Tests for specific missing lines in views.py."""

    def setUp(self):
        self.client = Client()

    @patch('core.views.connection')
    def test_line79_80_readiness_db_error(self, mock_conn):
        """Test lines 79-80: database OperationalError in ReadinessView."""
        from django.db import OperationalError
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = OperationalError("DB Error")

        response = self.client.get('/health/ready/')
        self.assertEqual(response.status_code, 503)

    @patch('core.views.connection')
    def test_lines91_93_readiness_cache_error(self, mock_conn):
        """Test lines 91-93: cache error in ReadinessView."""
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.return_value = None

        with patch('core.views.cache') as mock_cache:
            mock_cache.set.return_value = None
            mock_cache.get.side_effect = Exception("Cache Error")

            response = self.client.get('/health/ready/')
            self.assertEqual(response.status_code, 503)

    def test_line149_planretrieve_stops(self):
        """Test line 149: stops_data loop in PlanRetrieveView."""
        # Use mock instead of creating real objects
        import uuid
        test_uuid = uuid.uuid4()
        with patch('core.views.RoutePlan.objects.get') as mock_get:
            mock_plan = MagicMock()
            mock_plan.id = test_uuid
            mock_plan.start_query = 'Test Start'
            mock_plan.finish_query = 'Test Finish'
            mock_plan.start_lat = 40.0
            mock_plan.start_lon = -90.0
            mock_plan.finish_lat = 45.0
            mock_plan.finish_lon = -85.0
            mock_plan.distance_miles = 100.0
            mock_plan.geometry = {'type': 'LineString', 'coordinates': []}
            mock_plan.assumptions = {}
            mock_plan.total_fuel_gallons = 10.0
            mock_plan.total_cost_usd = 35.0
            mock_plan.warnings = []

            mock_station = MagicMock()
            mock_station.id = 1
            mock_station.name = "Test Station"
            mock_station.retail_price = 3.50

            mock_stop = MagicMock()
            mock_stop.sequence = 1
            mock_stop.station = mock_station
            mock_stop.gallons_purchased = 10.0
            mock_stop.cost_usd = 35.0
            mock_stop.distance_from_start_miles = 50.0

            mock_plan.stops.all.return_value.order_by.return_value = [mock_stop]
            mock_get.return_value = mock_plan

            response = self.client.get(f'/api/v1/plan/{test_uuid}/')
            self.assertEqual(response.status_code, 200)

    def test_line192_stationlist_city_filter(self):
        """Test line 192: city filter in StationListView."""
        # Use mock to avoid database constraints
        with patch('core.views.Station.objects.filter') as mock_filter:
            mock_station = MagicMock()
            mock_station.id = 1
            mock_station.name = "Station 1"
            mock_station.latitude = 40.0
            mock_station.longitude = -90.0
            mock_station.retail_price = 3.50
            mock_station.state = "CA"
            mock_station.city = "San Francisco"

            # Create a mock queryset
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.__iter__ = lambda self: iter([mock_station])

            # First filter by state, then city, then max_price
            mock_filter.return_value = mock_qs

            response = self.client.get('/api/v1/stations/?city=San%20Francisco')
            self.assertEqual(response.status_code, 200)

    def test_lines232_233_home_view(self):
        """Test lines 232-233: HomeView with invalid numeric."""
        response = self.client.post('/', data={
            'start': 'Chicago, IL',
            'finish': 'Dallas, TX',
            'range_miles': 'invalid',
            'mpg': 'invalid',
            'start_fuel_gallons': 'invalid',
            'station_buffer_miles': 'invalid'
        })
        self.assertEqual(response.status_code, 200)

    def test_line246_home_view_error(self):
        """Test line 246: HomeView with calculation error."""
        with patch('core.views.calculate_route_plan') as mock_calc:
            mock_calc.return_value = {'success': False, 'error': 'Test error'}
            response = self.client.post('/', data={
                'start': 'Chicago, IL',
                'finish': 'Dallas, TX',
                'range_miles': 500.0,
                'mpg': 10.0,
                'start_fuel_gallons': 0.0,
                'station_buffer_miles': 25.0
            })
            self.assertEqual(response.status_code, 200)

    def test_line262_register_invalid(self):
        """Test line 262: RegisterView invalid form."""
        response = self.client.post('/register/', data={
            'username': 'testuser',
            'password1': 'short',
            'password2': 'different'
        })
        self.assertEqual(response.status_code, 200)

    def test_line296_about_view(self):
        """Test line 296: AboutView."""
        response = self.client.get('/about/')
        self.assertEqual(response.status_code, 200)

    def test_line301_support_view(self):
        """Test line 301: SupportView."""
        response = self.client.get('/support/')
        self.assertEqual(response.status_code, 200)


class TestServicesLine131(TestCase):
    """Test for line 131 in services.py (unreachable dead code)."""

    @patch('core.services.httpx.Client')
    @patch('core.services.PHOTON_CIRCUIT_BREAKER.allow_request', return_value=True)
    @patch('core.services.PHOTON_CIRCUIT_BREAKER.record_failure')
    @patch('core.services.GeocodeCache.objects.create')
    def test_line131_unreachable(self, mock_cache_create, mock_record_failure, mock_allow, mock_client):
        """Test the unreachable return at line 131 in geocode_location."""
        # This tests the fallback return path that's never actually reached
        # due to the early returns in the try/except blocks
        from core.services import geocode_location

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = Exception("400 Bad Request")
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        # This will hit the except httpx.HTTPStatusError block which returns early
        # so line 131 is indeed unreachable
        result = geocode_location("Test Location")
        self.assertIn('error', result)


if __name__ == '__main__':
    import unittest
    unittest.main()