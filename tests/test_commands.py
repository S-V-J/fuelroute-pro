"""
Tests for management commands (import, geocode).
"""
import pytest
import csv
import io
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from core.models import Station, GeocodeCache, RouteCache


class TestImportStationsCommand(TestCase):
    """Test the import_stations management command."""

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

    def test_import_valid_csv(self):
        """Import should create stations from valid CSV."""
        csv_content = self.create_csv_content([
            {
                'OPIS Truckstop ID': '1',
                'Truckstop Name': 'Test Station',
                'Address': '123 Main St',
                'City': 'Chicago',
                'State': 'IL',
                'Rack ID': '100',
                'Retail Price': '3.50'
            }
        ])

        # Write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            call_command('import_stations', temp_path)
            self.assertEqual(Station.objects.count(), 1)
            station = Station.objects.first()
            self.assertEqual(station.name, 'Test Station')
            self.assertEqual(station.state, 'IL')
            self.assertEqual(float(station.retail_price), 3.50)
        finally:
            import os
            os.unlink(temp_path)

    def test_import_filters_non_us_states(self):
        """Import should skip Canadian provinces."""
        csv_content = self.create_csv_content([
            {
                'OPIS Truckstop ID': '1',
                'Truckstop Name': 'US Station',
                'Address': '123 Main St',
                'City': 'Chicago',
                'State': 'IL',
                'Rack ID': '100',
                'Retail Price': '3.50'
            },
            {
                'OPIS Truckstop ID': '2',
                'Truckstop Name': 'Canada Station',
                'Address': '456 Queen St',
                'City': 'Toronto',
                'State': 'ON',
                'Rack ID': '200',
                'Retail Price': '4.00'
            }
        ])

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            call_command('import_stations', temp_path)
            self.assertEqual(Station.objects.count(), 1)
            self.assertEqual(Station.objects.first().state, 'IL')
        finally:
            import os
            os.unlink(temp_path)

    def test_import_skips_missing_price(self):
        """Import should skip rows with missing price."""
        csv_content = self.create_csv_content([
            {
                'OPIS Truckstop ID': '1',
                'Truckstop Name': 'Valid Station',
                'Address': '123 Main St',
                'City': 'Chicago',
                'State': 'IL',
                'Rack ID': '100',
                'Retail Price': '3.50'
            },
            {
                'OPIS Truckstop ID': '2',
                'Truckstop Name': 'Invalid Station',
                'Address': '456 Main St',
                'City': 'Detroit',
                'State': 'MI',
                'Rack ID': '200',
                'Retail Price': ''
            }
        ])

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            call_command('import_stations', temp_path)
            self.assertEqual(Station.objects.count(), 1)
        finally:
            import os
            os.unlink(temp_path)

    def test_import_deduplicates_by_rack_id(self):
        """Import should deduplicate by Rack ID, keeping lowest price."""
        csv_content = self.create_csv_content([
            {
                'OPIS Truckstop ID': '1',
                'Truckstop Name': 'Station A',
                'Address': '123 Main St',
                'City': 'Chicago',
                'State': 'IL',
                'Rack ID': '100',
                'Retail Price': '3.50'
            },
            {
                'OPIS Truckstop ID': '2',
                'Truckstop Name': 'Station B',
                'Address': '123 Main St',
                'City': 'Chicago',
                'State': 'IL',
                'Rack ID': '100',
                'Retail Price': '3.00'
            }
        ])

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            call_command('import_stations', temp_path)
            self.assertEqual(Station.objects.count(), 1)
            station = Station.objects.first()
            self.assertEqual(float(station.retail_price), 3.00)  # Lower price kept
        finally:
            import os
            os.unlink(temp_path)

    def test_import_idempotent(self):
        """Running import twice should not create duplicates."""
        csv_content = self.create_csv_content([
            {
                'OPIS Truckstop ID': '1',
                'Truckstop Name': 'Test Station',
                'Address': '123 Main St',
                'City': 'Chicago',
                'State': 'IL',
                'Rack ID': '100',
                'Retail Price': '3.50'
            }
        ])

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            call_command('import_stations', temp_path)
            call_command('import_stations', temp_path)
            self.assertEqual(Station.objects.count(), 1)
        finally:
            import os
            os.unlink(temp_path)

    def test_import_handles_invalid_price(self):
        """Import should skip rows with invalid price."""
        csv_content = self.create_csv_content([
            {
                'OPIS Truckstop ID': '1',
                'Truckstop Name': 'Valid Station',
                'Address': '123 Main St',
                'City': 'Chicago',
                'State': 'IL',
                'Rack ID': '100',
                'Retail Price': '3.50'
            },
            {
                'OPIS Truckstop ID': '2',
                'Truckstop Name': 'Invalid Station',
                'Address': '456 Main St',
                'City': 'Detroit',
                'State': 'MI',
                'Rack ID': '200',
                'Retail Price': 'not-a-number'
            }
        ])

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            call_command('import_stations', temp_path)
            self.assertEqual(Station.objects.count(), 1)
        finally:
            import os
            os.unlink(temp_path)


class TestGeocodeStationsCommand(TestCase):
    """Test the geocode_stations management command."""

    @patch('core.management.commands.geocode_stations.httpx.Client')
    def test_geocode_success(self, mock_client_class):
        """Geocode should update station coordinates on success."""
        # Create station without coordinates
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

        # Mock HTTP response
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'features': [{
                'geometry': {'coordinates': [-87.6298, 41.8781]},
                'properties': {'name': 'Test Station'}
            }]
        }
        mock_client.get.return_value = mock_response

        call_command('geocode_stations', '--limit', '1')

        station.refresh_from_db()
        self.assertIsNotNone(station.latitude)
        self.assertIsNotNone(station.longitude)
        self.assertAlmostEqual(station.latitude, 41.8781, places=2)
        self.assertAlmostEqual(station.longitude, -87.6298, places=2)

    @patch('core.management.commands.geocode_stations.httpx.Client')
    def test_geocode_fallback_to_city_state(self, mock_client_class):
        """Geocode should fallback to city+state if name search fails."""
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

        # First call fails (name search), second succeeds (city+state)
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 200
        mock_response_fail.json.return_value = {'features': []}

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            'features': [{
                'geometry': {'coordinates': [-87.6298, 41.8781]},
                'properties': {'name': 'Chicago, IL'}
            }]
        }

        mock_client.get.side_effect = [mock_response_fail, mock_response_success]

        call_command('geocode_stations', '--limit', '1')

        station.refresh_from_db()
        self.assertIsNotNone(station.latitude)

    @patch('core.management.commands.geocode_stations.httpx.Client')
    def test_geocode_creates_cache_entry(self, mock_client_class):
        """Geocode should create GeocodeCache entries."""
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
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'features': [{
                'geometry': {'coordinates': [-87.6298, 41.8781]},
                'properties': {'name': 'Test Station'}
            }]
        }
        mock_client.get.return_value = mock_response

        call_command('geocode_stations', '--limit', '1')

        cache_entries = GeocodeCache.objects.all()
        self.assertEqual(cache_entries.count(), 1)
        self.assertTrue(cache_entries.first().is_success)


class TestGeocodeCacheModel(TestCase):
    """Test the GeocodeCache model."""

    def test_cache_normalized_query(self):
        """Cache should store normalized query."""
        cache = GeocodeCache.objects.create(
            query='  Chicago, IL  ',
            normalized_query='chicago, il',
            latitude=41.8781,
            longitude=-87.6298,
            provider='photon',
            is_success=True
        )
        self.assertEqual(cache.normalized_query, 'chicago, il')

    def test_cache_index_exists(self):
        """Cache should have indexes on normalized_query and provider."""
        # This test verifies the model has the right indexes defined
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA index_list('core_geocodecache')")
            indexes = cursor.fetchall()
            # Check that indexes exist on normalized_query and provider
            index_names = [idx[1] for idx in indexes]
            self.assertTrue(any('normalized_query' in name for name in index_names))
            self.assertTrue(any('provider' in name for name in index_names))


class TestRouteCacheModel(TestCase):
    """Test the RouteCache model."""

    def test_route_cache_creation(self):
        """RouteCache should store route geometry and metadata."""
        import hashlib
        route_hash = hashlib.sha256(b'test').hexdigest()

        cache = RouteCache.objects.create(
            route_hash=route_hash,
            start_lat=41.8781,
            start_lon=-87.6298,
            finish_lat=32.7767,
            finish_lon=-96.7970,
            distance_miles=925.4,
            duration_minutes=840.0,
            geometry_geojson={'type': 'LineString', 'coordinates': []},
            provider='osrm_public'
        )

        self.assertEqual(cache.route_hash, route_hash)
        self.assertEqual(cache.distance_miles, 925.4)
        self.assertEqual(cache.provider, 'osrm_public')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])