"""
Tests for models to achieve 100% coverage.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from core.models import (
    VehicleProfile, Station, GeocodeCache, RouteCache, RoutePlan, RouteStop
)
import uuid


class TestVehicleProfileModel(TestCase):
    """Test VehicleProfile model methods."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')

    def test_str_method(self):
        """Test __str__ method."""
        vehicle = VehicleProfile.objects.create(
            user=self.user,
            name='My Truck',
            mpg=10.0,
            tank_capacity_gallons=50.0
        )
        self.assertEqual(str(vehicle), 'My Truck (testuser)')

    def test_save_sets_default(self):
        """Test save method sets only one default per user."""
        v1 = VehicleProfile.objects.create(
            user=self.user, name='Truck 1', is_default=True
        )
        v2 = VehicleProfile.objects.create(
            user=self.user, name='Truck 2', is_default=True
        )
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertFalse(v1.is_default)
        self.assertTrue(v2.is_default)

    def test_save_not_default_doesnt_affect_others(self):
        """Test save with is_default=False doesn't affect other vehicles."""
        v1 = VehicleProfile.objects.create(
            user=self.user, name='Truck 1', is_default=True
        )
        v2 = VehicleProfile.objects.create(
            user=self.user, name='Truck 2', is_default=False
        )
        v1.refresh_from_db()
        self.assertTrue(v1.is_default)

    def test_save_update_without_is_default(self):
        """Test saving without changing is_default doesn't affect others."""
        v1 = VehicleProfile.objects.create(
            user=self.user, name='Truck 1', is_default=True
        )
        v1.mpg = 12.0
        v1.save()
        v1.refresh_from_db()
        self.assertTrue(v1.is_default)
        self.assertEqual(v1.mpg, 12.0)


class TestStationModel(TestCase):
    """Test Station model methods."""

    def test_str_method(self):
        """Test __str__ method."""
        station = Station.objects.create(
            opis_id=1,
            name='Test Station',
            address='123 Main St',
            city='Chicago',
            state='IL',
            rack_id=100,
            retail_price=3.50
        )
        expected = 'Test Station (Chicago, IL) - $3.500'
        self.assertEqual(str(station), expected)


class TestGeocodeCacheModel(TestCase):
    """Test GeocodeCache model methods."""

    def test_str_method_success(self):
        """Test __str__ method for successful geocode."""
        cache = GeocodeCache.objects.create(
            query='Chicago, IL',
            normalized_query='chicago, il',
            latitude=41.8781,
            longitude=-87.6298,
            provider='photon',
            is_success=True
        )
        self.assertEqual(str(cache), '[photon] Chicago, IL -> Success')

    def test_str_method_failure(self):
        """Test __str__ method for failed geocode."""
        cache = GeocodeCache.objects.create(
            query='Invalid Location',
            normalized_query='invalid location',
            provider='photon',
            is_success=False
        )
        self.assertEqual(str(cache), '[photon] Invalid Location -> Failed')


class TestRouteCacheModel(TestCase):
    """Test RouteCache model methods."""

    def test_str_method(self):
        """Test __str__ method."""
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
        expected = f'Route {route_hash[:8]}... (925.4 mi)'
        self.assertEqual(str(cache), expected)


class TestRoutePlanModel(TestCase):
    """Test RoutePlan model methods."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')

    def test_str_method(self):
        """Test __str__ method."""
        plan = RoutePlan.objects.create(
            user=self.user,
            id=uuid.uuid4(),
            start_query='Chicago, IL',
            start_lat=41.8781,
            start_lon=-87.6298,
            finish_query='Dallas, TX',
            finish_lat=32.7767,
            finish_lon=-96.7970,
            distance_miles=925.4,
            geometry='{}',
            total_fuel_gallons=92.5,
            total_cost_usd=285.45
        )
        expected = f'Plan {plan.id} (Chicago, IL to Dallas, TX)'
        self.assertEqual(str(plan), expected)


class TestRouteStopModel(TestCase):
    """Test RouteStop model methods."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.station = Station.objects.create(
            opis_id=1,
            name='Test Station',
            address='123 Main St',
            city='Chicago',
            state='IL',
            rack_id=100,
            retail_price=3.50
        )
        self.plan = RoutePlan.objects.create(
            user=self.user,
            id=uuid.uuid4(),
            start_query='Chicago, IL',
            start_lat=41.8781,
            start_lon=-87.6298,
            finish_query='Dallas, TX',
            finish_lat=32.7767,
            finish_lon=-96.7970,
            distance_miles=925.4,
            geometry='{}',
            total_fuel_gallons=92.5,
            total_cost_usd=285.45
        )

    def test_str_method(self):
        """Test __str__ method."""
        stop = RouteStop.objects.create(
            plan=self.plan,
            station=self.station,
            sequence=1,
            distance_from_start_miles=0.0,
            gallons_purchased=50.0,
            cost_usd=175.00
        )
        self.assertEqual(str(stop), 'Stop 1: Test Station')

    def test_ordering(self):
        """Test default ordering by sequence."""
        RouteStop.objects.create(plan=self.plan, station=self.station, sequence=2,
                                 distance_from_start_miles=100.0, gallons_purchased=25.0, cost_usd=50.0)
        RouteStop.objects.create(plan=self.plan, station=self.station, sequence=1,
                                 distance_from_start_miles=0.0, gallons_purchased=25.0, cost_usd=50.0)

        stops = list(RouteStop.objects.all())
        self.assertEqual(stops[0].sequence, 1)
        self.assertEqual(stops[1].sequence, 2)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])