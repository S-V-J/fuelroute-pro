"""
Additional tests for management commands to achieve 100% coverage.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO
from core.models import Station, GeocodeCache


class TestGeocodeStationsCommandCoverage(TestCase):
    """Test geocode_stations command edge cases for full coverage."""

    def setUp(self):
        # Clear existing stations
        Station.objects.all().delete()

    def test_geocode_no_stations_to_process(self):
        """Test early return when all stations already geocoded."""
        from io import StringIO
        from django.core.management import call_command

        # Create station with coordinates already set
        Station.objects.create(
            opis_id=1,
            name='Test Station',
            address='123 Main St',
            city='Chicago',
            state='IL',
            rack_id=100,
            retail_price=3.50,
            latitude=41.8781,
            longitude=-87.6298
        )

        out = StringIO()
        call_command('geocode_stations', stdout=out)

        output = out.getvalue()
        self.assertIn('All stations already geocoded', output)

    @patch('core.management.commands.geocode_stations.httpx.Client')
    def test_geocode_successful_fallback(self, mock_client_class):
        """Test successful geocoding via fallback (city+state)."""
        station = Station.objects.create(
            opis_id=1,
            name='Test Station',
            address='123 Main St',
            city='Chicago',
            state='IL',
            rack_id=100,
            retail_price=3.50,
            latitude=None,
            longitude=None
        )

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        # First call: empty features (triggers fallback)
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {'features': []}

        # Fallback call: successful
        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {
            'features': [{
                'geometry': {'coordinates': [-87.6298, 41.8781]}
            }]
        }

        mock_client.get.side_effect = [mock_response_1, mock_response_2]

        call_command('geocode_stations', '--limit', '1')

        station.refresh_from_db()
        self.assertIsNotNone(station.latitude)
        self.assertIsNotNone(station.longitude)
        self.assertAlmostEqual(station.latitude, 41.8781, places=2)
        self.assertAlmostEqual(station.longitude, -87.6298, places=2)

        cache_entries = GeocodeCache.objects.all()
        self.assertEqual(cache_entries.count(), 1)
        self.assertTrue(cache_entries.first().is_success)

    @patch('core.management.commands.geocode_stations.httpx.Client')
    def test_geocode_successful_direct(self, mock_client_class):
        """Test successful geocoding without fallback."""
        station = Station.objects.create(
            opis_id=1,
            name='Test Station',
            address='123 Main St',
            city='Chicago',
            state='IL',
            rack_id=100,
            retail_price=3.50,
            latitude=None,
            longitude=None
        )

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Direct successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'features': [{
                'geometry': {'coordinates': [-87.6298, 41.8781]}
            }]
        }
        mock_client.get.return_value = mock_response

        call_command('geocode_stations', '--limit', '1')

        station.refresh_from_db()
        self.assertIsNotNone(station.latitude)
        self.assertAlmostEqual(station.latitude, 41.8781, places=2)

        cache_entries = GeocodeCache.objects.all()
        self.assertEqual(cache_entries.count(), 1)
        self.assertTrue(cache_entries.first().is_success)

    @patch('core.management.commands.geocode_stations.httpx.Client')
    def test_geocode_handles_no_features_found(self, mock_client_class):
        """Test when Photon returns no features and fallback also fails."""
        station = Station.objects.create(
            opis_id=1,
            name='Test Station',
            address='123 Main St',
            city='Chicago',
            state='IL',
            rack_id=100,
            retail_price=3.50,
            latitude=None,
            longitude=None
        )

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        # First call: empty features
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {'features': []}

        # Second call (fallback): also empty features
        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {'features': []}

        mock_client.get.side_effect = [mock_response_1, mock_response_2]

        call_command('geocode_stations', '--limit', '1')

        station.refresh_from_db()
        self.assertIsNone(station.latitude)
        self.assertIsNone(station.longitude)

        # Should have cache entry with is_success=False
        cache_entries = GeocodeCache.objects.all()
        self.assertEqual(cache_entries.count(), 1)
        self.assertFalse(cache_entries.first().is_success)

    @patch('core.management.commands.geocode_stations.httpx.Client')
    def test_geocode_handles_400_error(self, mock_client_class):
        """Test handling of 400 HTTP error."""
        station = Station.objects.create(
            opis_id=1,
            name='Test Station',
            address='123 Main St',
            city='Chicago',
            state='IL',
            rack_id=100,
            retail_price=3.50,
            latitude=None,
            longitude=None
        )

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'error': 'Bad Request'}
        mock_client.get.return_value = mock_response

        call_command('geocode_stations', '--limit', '1')

        station.refresh_from_db()
        self.assertIsNone(station.latitude)

        cache_entries = GeocodeCache.objects.all()
        self.assertEqual(cache_entries.count(), 1)
        self.assertFalse(cache_entries.first().is_success)

    @patch('core.management.commands.geocode_stations.httpx.Client')
    def test_geocode_handles_http_error(self, mock_client_class):
        """Test handling of HTTP error exception."""
        import httpx
        station = Station.objects.create(
            opis_id=1,
            name='Test Station',
            address='123 Main St',
            city='Chicago',
            state='IL',
            rack_id=100,
            retail_price=3.50,
            latitude=None,
            longitude=None
        )

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = httpx.HTTPError("Connection failed")

        call_command('geocode_stations', '--limit', '1')

        station.refresh_from_db()
        self.assertIsNone(station.latitude)

        cache_entries = GeocodeCache.objects.all()
        self.assertEqual(cache_entries.count(), 1)
        self.assertFalse(cache_entries.first().is_success)
        self.assertIn('error', cache_entries.first().raw_response)

    @patch('core.management.commands.geocode_stations.httpx.Client')
    def test_geocode_handles_generic_exception(self, mock_client_class):
        """Test handling of generic exception."""
        station = Station.objects.create(
            opis_id=1,
            name='Test Station',
            address='123 Main St',
            city='Chicago',
            state='IL',
            rack_id=100,
            retail_price=3.50,
            latitude=None,
            longitude=None
        )

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = Exception("Unexpected error")

        call_command('geocode_stations', '--limit', '1')

        station.refresh_from_db()
        self.assertIsNone(station.latitude)

        cache_entries = GeocodeCache.objects.all()
        self.assertEqual(cache_entries.count(), 1)
        self.assertFalse(cache_entries.first().is_success)
        self.assertIn('error', cache_entries.first().raw_response)


class TestWarmCacheCommandCoverage(TestCase):
    """Test warm_cache command for full coverage."""

    @patch('core.management.commands.warm_cache.geocode_location')
    @patch('core.management.commands.warm_cache.get_driving_route')
    def test_warm_cache_handles_start_geocode_failure(self, mock_route, mock_geo):
        """Test warm_cache handles start geocode failures gracefully."""
        from core.management.commands.warm_cache import Command
        from io import StringIO

        mock_geo.return_value = {'success': False, 'error': 'Not found'}
        mock_route.return_value = {'success': True, 'distance_miles': 100.0}

        cmd = Command()
        out = StringIO()
        cmd.stdout = out
        cmd.handle()

        output = out.getvalue()
        self.assertIn('Cache warming complete', output)

    @patch('core.management.commands.warm_cache.geocode_location')
    @patch('core.management.commands.warm_cache.get_driving_route')
    def test_warm_cache_handles_finish_geocode_failure(self, mock_route, mock_geo):
        """Test warm_cache handles finish geocode failures gracefully."""
        from core.management.commands.warm_cache import Command
        from io import StringIO

        # We need enough values for all 14 calls (7 routes * 2 geocodes each)
        # Pattern: start succeeds, finish fails, then repeat
        mock_geo.side_effect = [
            {'success': True, 'lat': 40.0, 'lon': -75.0, 'cached': False},
            {'success': False, 'error': 'Not found'},
        ] * 7
        mock_route.return_value = {'success': True, 'distance_miles': 100.0}

        cmd = Command()
        out = StringIO()
        cmd.stdout = out
        cmd.handle()

        output = out.getvalue()
        self.assertIn('Cache warming complete', output)

    @patch('core.management.commands.warm_cache.geocode_location')
    @patch('core.management.commands.warm_cache.get_driving_route')
    def test_warm_cache_handles_route_failure(self, mock_route, mock_geo):
        """Test warm_cache handles route failures gracefully."""
        from core.management.commands.warm_cache import Command
        from io import StringIO

        mock_geo.return_value = {'success': True, 'lat': 40.0, 'lon': -75.0, 'cached': False}
        mock_route.return_value = {'success': False, 'error': 'Route not found'}

        cmd = Command()
        out = StringIO()
        cmd.stdout = out
        cmd.handle()

        output = out.getvalue()
        self.assertIn('Cache warming complete', output)
        # Check for failure indicator in output
        self.assertTrue('failures:' in output.lower())

    @patch('core.management.commands.warm_cache.geocode_location')
    @patch('core.management.commands.warm_cache.get_driving_route')
    @patch('time.sleep', return_value=None)
    def test_warm_cache_full_execution(self, mock_sleep, mock_route, mock_geo):
        """Test full warm_cache execution path."""
        from core.management.commands.warm_cache import Command
        from io import StringIO

        mock_geo.return_value = {'success': True, 'lat': 40.0, 'lon': -75.0, 'cached': False}
        mock_route.return_value = {'success': True, 'distance_miles': 100.0, 'cached': True}

        cmd = Command()
        out = StringIO()
        cmd.stdout = out
        cmd.handle()

        output = out.getvalue()
        self.assertIn('Cache warming complete', output)
        self.assertIn('geocode', output.lower())
        self.assertIn('route', output.lower())
        # Verify sleep was called (rate limiting)
        self.assertTrue(mock_sleep.called)


class TestImportStationsEdgeCases(TestCase):
    """Additional import_stations tests for edge cases."""

    def create_csv_content(self, rows):
        """Create CSV content from list of dicts."""
        if not rows:
            return ''
        fieldnames = rows[0].keys()
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def test_import_with_whitespace_in_state(self):
        """Import should handle whitespace in state field."""
        import tempfile, csv, io, os
        
        rows = [{
            'OPIS Truckstop ID': '1',
            'Truckstop Name': 'Test Station',
            'Address': '123 Main St',
            'City': 'Chicago',
            'State': '  IL  ',  # Whitespace
            'Rack ID': '100',
            'Retail Price': '3.50'
        }]
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        csv_content = output.getvalue()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            call_command('import_stations', temp_path)
            self.assertEqual(Station.objects.count(), 1)
            station = Station.objects.first()
            self.assertEqual(station.state, 'IL')
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
