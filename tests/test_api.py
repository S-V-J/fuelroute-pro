"""
Tests for the API endpoints.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import Station, RoutePlan, RouteStop


class TestHealthEndpoint(TestCase):
    """Test the health check endpoint."""

    def setUp(self):
        self.client = Client()

    def test_health_endpoint_returns_ok(self):
        """Health endpoint should return 200 with status ok."""
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('django_version', data)
        self.assertIn('database_reachable', data)
        self.assertIn('fuel_station_count', data)


class TestStatsEndpoint(TestCase):
    """Test the platform stats endpoint."""

    def setUp(self):
        self.client = Client()

    def test_stats_endpoint_returns_data(self):
        """Stats endpoint should return station count and plan count."""
        response = self.client.get('/api/v1/stats/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('station_count', data)
        self.assertIn('total_plans', data)
        self.assertIn('avg_savings', data)
        self.assertIn('avg_response_time', data)


class TestPlanEndpoint(TestCase):
    """Test the route planning endpoint."""

    def setUp(self):
        self.client = Client()

    @patch('core.views.calculate_route_plan')
    def test_plan_endpoint_valid_request(self, mock_calculate):
        """Valid plan request should return route data."""
        mock_calculate.return_value = {
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
            data=json.dumps({'start': 'Chicago, IL', 'finish': 'Dallas, TX'}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['start']['query'], 'Chicago, IL')

    def test_plan_endpoint_missing_start(self):
        """Missing start should return 400."""
        response = self.client.post(
            '/api/v1/plan/',
            data=json.dumps({'finish': 'Dallas, TX'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)

    def test_plan_endpoint_missing_finish(self):
        """Missing finish should return 400."""
        response = self.client.post(
            '/api/v1/plan/',
            data=json.dumps({'start': 'Chicago, IL'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_plan_endpoint_invalid_json(self):
        """Invalid JSON should return 400."""
        response = self.client.post(
            '/api/v1/plan/',
            data='not json',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    @patch('core.views.calculate_route_plan')
    def test_plan_endpoint_with_coordinates(self, mock_calculate):
        """Plan request with coordinates should work."""
        mock_calculate.return_value = {
            'success': True,
            'plan_id': 'test-id',
            'start': {'query': '41.8781,-87.6298', 'lat': 41.8781, 'lon': -87.6298},
            'finish': {'query': '32.7767,-96.7970', 'lat': 32.7767, 'lon': -96.7970},
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
                'start': {'lat': 41.8781, 'lon': -87.6298},
                'finish': {'lat': 32.7767, 'lon': -96.7970}
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

    @patch('core.views.calculate_route_plan')
    def test_plan_endpoint_custom_vehicle(self, mock_calculate):
        """Plan request with custom vehicle params should pass them through."""
        mock_calculate.return_value = {
            'success': True,
            'plan_id': 'test-id',
            'start': {'query': 'Chicago, IL', 'lat': 41.8781, 'lon': -87.6298},
            'finish': {'query': 'Dallas, TX', 'lat': 32.7767, 'lon': -96.7970},
            'route': {'distance_miles': 925.4, 'geometry': {'type': 'LineString', 'coordinates': []}},
            'assumptions': {'range_miles': 300, 'mpg': 15.0, 'start_fuel_gallons': 10.0},
            'stops': [],
            'totals': {'fuel_gallons_purchased': 61.7, 'fuel_cost_usd': 190.30, 'stop_count': 0},
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
                'start_fuel_gallons': 10.0
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        # Verify the mock was called with custom params
        call_args = mock_calculate.call_args
        self.assertEqual(call_args[1]['range_miles'], 300.0)
        self.assertEqual(call_args[1]['mpg'], 15.0)
        self.assertEqual(call_args[1]['start_fuel_gallons'], 10.0)


class TestPlanRetrieveEndpoint(TestCase):
    """Test the plan retrieval endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.plan = RoutePlan.objects.create(
            user=self.user,
            start_query='Chicago, IL',
            start_lat=41.8781,
            start_lon=-87.6298,
            finish_query='Dallas, TX',
            finish_lat=32.7767,
            finish_lon=-96.7970,
            distance_miles=925.4,
            geometry='{"type": "LineString", "coordinates": []}',
            assumptions={'range_miles': 500, 'mpg': 10.0},
            warnings=[],
            total_fuel_gallons=92.5,
            total_cost_usd=285.45
        )

    def test_retrieve_existing_plan(self):
        """Should retrieve existing plan by ID."""
        response = self.client.get(f'/api/v1/plan/{self.plan.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['plan_id'], str(self.plan.id))

    def test_retrieve_nonexistent_plan(self):
        """Should return 404 for nonexistent plan."""
        import uuid
        fake_id = uuid.uuid4()
        response = self.client.get(f'/api/v1/plan/{fake_id}/')
        self.assertEqual(response.status_code, 404)


class TestStationListEndpoint(TestCase):
    """Test the station list endpoint."""

    def setUp(self):
        self.client = Client()
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

    def test_station_list_returns_paginated(self):
        """Station list should return paginated results."""
        response = self.client.get('/api/v1/stations/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertIn('count', data)

    def test_station_list_filter_by_state(self):
        """Station list should filter by state."""
        response = self.client.get('/api/v1/stations/?state=IL')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for station in data['results']:
            self.assertEqual(station['state'], 'IL')

    def test_station_list_filter_by_max_price(self):
        """Station list should filter by max price."""
        response = self.client.get('/api/v1/stations/?max_price=3.00')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for station in data['results']:
            self.assertLessEqual(float(station['retail_price']), 3.00)


class TestProviderMetadataEndpoint(TestCase):
    """Test the provider metadata endpoint."""

    def setUp(self):
        self.client = Client()

    def test_provider_metadata_returns_info(self):
        """Provider metadata should return active providers and defaults."""
        response = self.client.get('/api/v1/providers/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('routing_provider', data)
        self.assertIn('geocode_provider', data)
        self.assertIn('defaults', data)
        self.assertIn('api_keys_configured', data)


class TestHomeView(TestCase):
    """Test the home page view."""

    def setUp(self):
        self.client = Client()

    def test_home_page_loads(self):
        """Home page should load successfully."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'FuelRoute Pro')

    def test_home_page_post_valid(self):
        """Home page POST with valid data should return results."""
        import uuid
        test_plan_id = str(uuid.uuid4())
        with patch('core.views.calculate_route_plan') as mock_calc:
            mock_calc.return_value = {
                'success': True,
                'plan_id': test_plan_id,
                'start': {'query': 'Chicago, IL', 'lat': 41.8781, 'lon': -87.6298},
                'finish': {'query': 'Dallas, TX', 'lat': 32.7767, 'lon': -96.7970},
                'route': {'distance_miles': 925.4, 'geometry': {'type': 'LineString', 'coordinates': []}},
                'assumptions': {'range_miles': 500, 'mpg': 10.0},
                'stops': [],
                'totals': {'fuel_gallons_purchased': 92.5, 'fuel_cost_usd': 285.45, 'stop_count': 0},
                'warnings': [],
                'cache': {'route_cached': False, 'geocode_cached': False}
            }
            response = self.client.post('/', {
                'start': 'Chicago, IL',
                'finish': 'Dallas, TX'
            })
            self.assertEqual(response.status_code, 200)

    def test_home_page_post_missing_data(self):
        """Home page POST with missing data should return error."""
        response = self.client.post('/', {
            'start': 'Chicago, IL'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Route Calculation Failed')


class TestAuthViews(TestCase):
    """Test authentication views."""

    def setUp(self):
        self.client = Client()

    def test_login_page_loads(self):
        """Login page should load."""
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)

    def test_register_page_loads(self):
        """Register page should load."""
        response = self.client.get('/register/')
        self.assertEqual(response.status_code, 200)

    def test_register_creates_user(self):
        """Registration should create a new user."""
        response = self.client.post('/register/', {
            'username': 'newuser',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect to dashboard
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_login_logout_cycle(self):
        """User can log in and log out."""
        user = User.objects.create_user(username='testuser', password='testpass')
        response = self.client.post('/login/', {
            'username': 'testuser',
            'password': 'testpass'
        })
        self.assertEqual(response.status_code, 302)  # Redirect to dashboard

        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

        response = self.client.post('/logout/')
        self.assertEqual(response.status_code, 302)  # Redirect to home

        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 302)  # Redirect to login


class TestDashboardView(TestCase):
    """Test the dashboard view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')

    def test_dashboard_loads(self):
        """Dashboard should load for authenticated user."""
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome back')

    def test_dashboard_requires_login(self):
        """Dashboard should redirect unauthenticated users."""
        self.client.logout()
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 302)  # Redirect to login


class TestExportEndpoints(TestCase):
    """Test CSV and GeoJSON export endpoints."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')

        self.plan = RoutePlan.objects.create(
            user=self.user,
            start_query='Chicago, IL',
            start_lat=41.8781,
            start_lon=-87.6298,
            finish_query='Dallas, TX',
            finish_lat=32.7767,
            finish_lon=-96.7970,
            distance_miles=925.4,
            geometry='{"type": "LineString", "coordinates": []}',
            assumptions={'range_miles': 500, 'mpg': 10.0},
            warnings=[],
            total_fuel_gallons=92.5,
            total_cost_usd=285.45
        )
        self.station = Station.objects.create(
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
        RouteStop.objects.create(
            plan=self.plan,
            station=self.station,
            sequence=1,
            distance_from_start_miles=100.0,
            gallons_purchased=10.0,
            cost_usd=35.00
        )

    def test_export_csv(self):
        """CSV export should return CSV content."""
        response = self.client.get(f'/dashboard/export/csv/{self.plan.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8')
        self.assertIn('Test Station', content)
        self.assertIn('3.5', content)  # Price is formatted as 3.5 not 3.50
        self.assertIn('35.0', content)  # Cost is formatted as 35.0 not 35.00

    def test_export_geojson(self):
        """GeoJSON export should return GeoJSON content."""
        response = self.client.get(f'/dashboard/export/geojson/{self.plan.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertEqual(data['type'], 'LineString')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])