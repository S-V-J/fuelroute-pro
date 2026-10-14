"""
Tests for services to achieve 100% coverage.
"""
from django.test import TestCase, override_settings
from unittest.mock import Mock, patch, MagicMock, PropertyMock
import httpx
import time
from core.services import (
    CircuitBreaker, normalize_query, geocode_location, _geocode_fallback_census,
    get_driving_route, _get_routing_providers, _try_routing_provider,
    _route_osrm, _route_ors, _route_graphhopper, _record_provider_success,
    calculate_route_plan,
    PHOTON_CIRCUIT_BREAKER, CENSUS_CIRCUIT_BREAKER,
    OSRM_CIRCUIT_BREAKER, ORS_CIRCUIT_BREAKER, GRAPHHOPPER_CIRCUIT_BREAKER,
)
from core.models import RoutePlan, RouteStop
from core.models import Station, GeocodeCache, RouteCache


class TestNormalizeQuery(TestCase):
    """Test normalize_query function."""

    def test_normalize_simple(self):
        self.assertEqual(normalize_query('Chicago, IL'), 'chicago il')

    def test_normalize_case(self):
        self.assertEqual(normalize_query('CHICAGO, IL'), 'chicago il')

    def test_normalize_extra_spaces(self):
        self.assertEqual(normalize_query('  Chicago   IL  '), 'chicago il')

    def test_normalize_comma(self):
        self.assertEqual(normalize_query('Chicago,IL'), 'chicago il')


class TestCircuitBreaker(TestCase):
    """Test CircuitBreaker class."""

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

    def test_open_prevents_requests(self):
        """Test that open circuit breaker prevents requests."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        cb.open = True
        cb.last_failure = time.time()  # Recent failure
        self.assertFalse(cb.allow_request())

    def test_abstract_routing_provider_raises_not_implemented(self):
        from core.services import RoutingProvider
        provider = RoutingProvider()
        with self.assertRaises(NotImplementedError):
            provider.route(0, 0, 0, 0)

    def test_abstract_geocode_provider_raises_not_implemented(self):
        from core.services import GeocodeProvider
        provider = GeocodeProvider()
        with self.assertRaises(NotImplementedError):
            provider.geocode('test')


class TestGeocodeLocation(TestCase):
    """Test geocode_location function."""

    def setUp(self):
        GeocodeCache.objects.all().delete()
        PHOTON_CIRCUIT_BREAKER.failures = 0
        PHOTON_CIRCUIT_BREAKER.open = False
        CENSUS_CIRCUIT_BREAKER.failures = 0
        CENSUS_CIRCUIT_BREAKER.open = False

    @patch('core.services.httpx.Client')
    def test_geocode_cache_hit(self, mock_client_class):
        """Should return cached result if available."""
        GeocodeCache.objects.create(
            query='Chicago, IL',
            normalized_query='chicago il',
            latitude=41.8781,
            longitude=-87.6298,
            provider='photon',
            is_success=True
        )

        result = geocode_location('Chicago, IL')

        self.assertTrue(result['success'])
        self.assertEqual(result['lat'], 41.8781)
        self.assertEqual(result['lon'], -87.6298)
        self.assertTrue(result['cached'])

    @patch('core.services.httpx.Client')
    def test_geocode_success_photon(self, mock_client_class):
        """Should geocode successfully with Photon."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'features': [{
                'geometry': {'coordinates': [-87.6298, 41.8781]},
                'properties': {'name': 'Chicago, IL'}
            }]
        }
        mock_client.get.return_value = mock_response

        result = geocode_location('Chicago, IL')

        self.assertTrue(result['success'])
        self.assertAlmostEqual(result['lat'], 41.8781, places=2)
        self.assertAlmostEqual(result['lon'], -87.6298, places=2)
        self.assertFalse(result['cached'])

        # Should have created cache entry
        self.assertEqual(GeocodeCache.objects.count(), 1)

    @patch('core.services.httpx.Client')
    def test_geocode_not_found(self, mock_client_class):
        """Should handle location not found."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'features': []}
        mock_client.get.return_value = mock_response

        result = geocode_location('Invalid Location')

        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'].lower())

    @patch('core.services.httpx.Client')
    def test_geocode_http_error(self, mock_client_class):
        """Should handle HTTP error with retry."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.get.return_value = mock_response
        mock_client.get.side_effect = [
            httpx.HTTPError("Server error"),
            httpx.HTTPError("Server error"),
        ]

        result = geocode_location('Chicago, IL')

        self.assertFalse(result['success'])
        self.assertIn('geocoding failed after retries', result['error'].lower())

    @patch('core.services.httpx.Client')
    def test_geocode_400_fallback_to_census(self, mock_client_class):
        """Should fallback to Census on 400 error."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_client.get.return_value = mock_response

        with patch('core.services._geocode_fallback_census') as mock_fallback:
            mock_fallback.return_value = {'success': True, 'lat': 41.8781, 'lon': -87.6298, 'cached': False}
            result = geocode_location('Chicago, IL')
            mock_fallback.assert_called_once()

    @patch('core.services.httpx.Client')
    def test_geocode_exception(self, mock_client_class):
        """Should handle generic exception."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = Exception("Unexpected error")

        result = geocode_location('Chicago, IL')

        self.assertFalse(result['success'])
        self.assertIn('geocoding failed after retries', result['error'].lower())

    @patch('core.services.httpx.Client')
    def test_geocode_photon_circuit_breaker_open(self, mock_client_class):
        """Should handle Photon circuit breaker open and fallback to Census."""
        # Set Photon circuit breaker to open
        PHOTON_CIRCUIT_BREAKER.open = True
        PHOTON_CIRCUIT_BREAKER.last_failure = time.time()

        # Mock the Census fallback to succeed
        with patch('core.services._geocode_fallback_census') as mock_fallback:
            mock_fallback.return_value = {
                'success': True, 'lat': 41.8781, 'lon': -87.6298, 'cached': False
            }

            result = geocode_location('Chicago, IL')

            # Should call the fallback
            mock_fallback.assert_called_once_with('Chicago, IL', 'chicago il')
            self.assertTrue(result['success'])
            self.assertEqual(result['lat'], 41.8781)
            self.assertEqual(result['lon'], -87.6298)

    @patch('core.services.httpx.Client')
    def test_geocode_http_status_error_retry(self, mock_client_class):
        """Should handle HTTPStatusError with retry attempt."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 400

        # First call raises HTTPStatusError, second call also raises it
        mock_client.get.side_effect = [
            httpx.HTTPStatusError("400 Bad Request", request=MagicMock(), response=mock_response),
            httpx.HTTPStatusError("400 Bad Request", request=MagicMock(), response=mock_response),
        ]

        result = geocode_location('Chicago, IL')

        self.assertFalse(result['success'])
        # On first HTTPStatusError, it tries Census fallback; if Census also fails, returns "Location not found"
        self.assertIn('location not found', result['error'].lower())
        self.assertEqual(mock_client.get.call_count, 2)

    @patch('core.services.httpx.Client')
    def test_geocode_http_status_error_then_http_error(self, mock_client_class):
        """Should handle HTTPStatusError then fallback fails (tests fallback path lines 117-120)."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        # First attempt: 400 response -> raises HTTPStatusError internally -> triggers Census fallback
        mock_response_400 = MagicMock()
        mock_response_400.status_code = 400
        mock_client.get.return_value = mock_response_400

        with patch('core.services._geocode_fallback_census') as mock_fallback:
            mock_fallback.return_value = {'success': False, 'error': 'Census failed'}

            result = geocode_location('Chicago, IL')
            self.assertFalse(result['success'])
            self.assertIn('census failed', result['error'].lower())
            mock_fallback.assert_called_once_with('Chicago, IL', 'chicago il')
            self.assertFalse(result['success'])
            # Census fallback error is returned
            self.assertIn('census failed', result['error'].lower())
            mock_fallback.assert_called_once_with('Chicago, IL', 'chicago il')

    @patch('core.services.httpx.Client')
    def test_geocode_http_error_then_http_status_error(self, mock_client_class):
        """Should handle HTTPError then HTTPStatusError (lines 118-120)."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        # First attempt: HTTPError (continues to retry)
        # Second attempt: HTTPStatusError (hits lines 118-120)
        mock_client.get.side_effect = [
            httpx.HTTPError("HTTP error"),
            MagicMock(status_code=400)  # This will raise HTTPStatusError internally
        ]

        result = geocode_location('Chicago, IL')
        self.assertFalse(result['success'])
        # Both errors now fall through to final return
        self.assertIn('geocoding failed after retries', result['error'].lower())
        # Verify we attempted twice
        self.assertEqual(mock_client.get.call_count, 2)

    @patch('core.services.httpx.Client')
    def test_geocode_multiple_http_errors(self, mock_client_class):
        """Should handle HTTP errors and return failure (tests HTTPError path lines 125-127)."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        # First HTTPError triggers retry (sleep), second returns failure
        mock_client.get.side_effect = [
            httpx.HTTPError("First error"),
            httpx.HTTPError("Final error")
        ]

        result = geocode_location('Chicago, IL')
        self.assertFalse(result['success'])
        # Both errors now fall through to final return
        self.assertIn('geocoding failed after retries', result['error'].lower())

    @patch('core.services.httpx.Client')
    def test_geocode_http_error_after_retry(self, mock_client_class):
        """Should handle HTTP error on second attempt - triggers record_failure (lines 125-127)."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        # First attempt: HTTP error (triggers retry), Second attempt: HTTP error again (records failure)
        mock_client.get.side_effect = [
            httpx.HTTPError("First error"),
            httpx.HTTPError("Second error"),
        ]

        result = geocode_location('Chicago, IL')

        self.assertFalse(result['success'])
        self.assertIn('geocoding failed after retries', result['error'].lower())
        # Should have recorded failure and created cache entry
        cache = GeocodeCache.objects.filter(provider='photon', is_success=False).first()
        self.assertIsNotNone(cache)
        self.assertEqual(mock_client.get.call_count, 2)

    @patch('core.services.httpx.Client')
    def test_geocode_photon_circuit_breaker_open(self, mock_client_class):
        """Should handle Photon circuit breaker open and fallback to Census."""
        # Set Photon circuit breaker to open
        PHOTON_CIRCUIT_BREAKER.open = True
        PHOTON_CIRCUIT_BREAKER.last_failure = time.time()

        # Mock the Census fallback to succeed
        with patch('core.services._geocode_fallback_census') as mock_fallback:
            mock_fallback.return_value = {
                'success': True, 'lat': 41.8781, 'lon': -87.6298, 'cached': False
            }

            result = geocode_location('Chicago, IL')

            # Should call the fallback
            mock_fallback.assert_called_once_with('Chicago, IL', 'chicago il')
            self.assertTrue(result['success'])
            self.assertEqual(result['lat'], 41.8781)
            self.assertEqual(result['lon'], -87.6298)


class TestGeocodeFallbackCensus(TestCase):
    """Test _geocode_fallback_census function."""

    def setUp(self):
        CENSUS_CIRCUIT_BREAKER.failures = 0
        CENSUS_CIRCUIT_BREAKER.open = False
        GeocodeCache.objects.all().delete()

    @patch('core.services.httpx.Client')
    def test_census_success(self, mock_client_class):
        """Should geocode successfully with Census."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'result': {
                'addressMatches': [{
                    'coordinates': {'x': -87.6298, 'y': 41.8781}
                }]
            }
        }
        mock_client.get.return_value = mock_response

        result = _geocode_fallback_census('Chicago, IL', 'chicago il')

        self.assertTrue(result['success'])
        self.assertAlmostEqual(result['lat'], 41.8781, places=2)
        self.assertAlmostEqual(result['lon'], -87.6298, places=2)

    @patch('core.services.httpx.Client')
    def test_census_no_matches(self, mock_client_class):
        """Should handle no matches from Census."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'result': {'addressMatches': []}}
        mock_client.get.return_value = mock_response

        result = _geocode_fallback_census('Invalid Location', 'invalid location')

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Location not found')

    @patch('core.services.httpx.Client')
    def test_census_exception(self, mock_client_class):
        """Should handle Census exception."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = Exception("Census error")

        result = _geocode_fallback_census('Chicago, IL', 'chicago il')

        self.assertFalse(result['success'])

    def test_census_circuit_breaker_open(self):
        """Should handle Census circuit breaker open."""
        CENSUS_CIRCUIT_BREAKER.open = True
        CENSUS_CIRCUIT_BREAKER.last_failure = time.time()

        result = _geocode_fallback_census('Chicago, IL', 'chicago il')

        self.assertFalse(result['success'])
        # When circuit breaker is open, it returns "Location not found" after caching
        self.assertIn('location', result['error'].lower())


class TestGetRoutingProviders(TestCase):
    """Test _get_routing_providers function."""

    @override_settings(
        OSRM_SELF_HOSTED_URL='http://local-osrm:5000',
        OPENROUTESERVICE_API_KEY='ors-key',
        GRAPHHOPPER_API_KEY='gh-key',
        OSRM_PUBLIC_URL='https://router.project-osrm.org'
    )
    def test_get_all_providers(self):
        """Should return all configured providers in order."""
        providers = _get_routing_providers()
        names = [p[0] for p in providers]
        self.assertEqual(names, ['osrm_local', 'openrouteservice', 'graphhopper', 'osrm_public'])

    @override_settings(
        OSRM_SELF_HOSTED_URL='',
        OPENROUTESERVICE_API_KEY='',
        GRAPHHOPPER_API_KEY='',
        OSRM_PUBLIC_URL='https://router.project-osrm.org'
    )
    def test_get_only_public_osrm(self):
        """Should return only public OSRM when no keys configured."""
        providers = _get_routing_providers()
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0][0], 'osrm_public')

    @override_settings(
        OSRM_SELF_HOSTED_URL='',
        OPENROUTESERVICE_API_KEY='',
        GRAPHHOPPER_API_KEY='',
        OSRM_PUBLIC_URL='https://router.project-osrm.org'
    )
    def test_get_all_providers_except_public_osrm(self):
        """Should return all providers except public OSRM when no API keys configured."""
        providers = _get_routing_providers()
        # With only OSRM_PUBLIC_URL set, we should get only osrm_public
        self.assertEqual(len(providers), 1)
        names = [p[0] for p in providers]
        self.assertIn('osrm_public', names)
        self.assertNotIn('osrm_local', names)
        self.assertNotIn('openrouteservice', names)
        self.assertNotIn('graphhopper', names)

    def test_get_all_providers_with_different_configurations(self):
        """Test various combinations of provider configurations."""
        # Only OSRM public URL configured
        with override_settings(OSRM_PUBLIC_URL=''):
            providers = _get_routing_providers()
            self.assertEqual(len(providers), 1)
            self.assertEqual(providers[0][0], 'osrm_public')

        # Only OpenRouteService API key configured
        with override_settings(OPENROUTESERVICE_API_KEY='test-key'):
            providers = _get_routing_providers()
            self.assertEqual(len(providers), 2)
            names = [p[0] for p in providers]
            self.assertIn('openrouteservice', names)
            self.assertIn('osrm_public', names)
            self.assertNotIn('osrm_local', names)
            self.assertNotIn('graphhopper', names)

        # Only GraphHopper API key configured
        with override_settings(OPENROUTESERVICE_API_KEY='', GRAPHHOPPER_API_KEY='gh-key'):
            providers = _get_routing_providers()
            self.assertEqual(len(providers), 2)
            names = [p[0] for p in providers]
            self.assertIn('graphhopper', names)
            self.assertNotIn('osrm_local', names)
            self.assertNotIn('openrouteservice', names)
            self.assertIn('osrm_public', names)

    @override_settings(
        OSRM_SELF_HOSTED_URL='http://local-osrm:5000',
        OPENROUTESERVICE_API_KEY='ors-key',
        GRAPHHOPPER_API_KEY='gh-key',
        OSRM_PUBLIC_URL='https://router.project-osrm.org'
    )
    def test_get_all_providers_with_multiple_configs(self):
        """Test when multiple providers are configured."""
        providers = _get_routing_providers()
        self.assertEqual(len(providers), 4)
        names = [p[0] for p in providers]
        self.assertEqual(names, ['osrm_local', 'openrouteservice', 'graphhopper', 'osrm_public'])

    def test_get_providers_with_empty_configuration(self):
        """Test when no provider configurations are set."""
        # This will use only OSRM_PUBLIC_URL by default
        providers = _get_routing_providers()
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0][0], 'osrm_public')


class TestTryRoutingProvider(TestCase):
    """Test _try_routing_provider function."""

    def test_osrm_local(self):
        """Should call _route_osrm for osrm_local."""
        with patch('core.services._route_osrm') as mock_route:
            mock_route.return_value = {'success': True, 'distance_miles': 100}
            result = _try_routing_provider('osrm_local', {'url': 'http://test'}, 40, -75, 41, -74)
            mock_route.assert_called_once()

    def test_openrouteservice(self):
        """Should call _route_ors for openrouteservice."""
        with patch('core.services._route_ors') as mock_route:
            mock_route.return_value = {'success': True, 'distance_miles': 100}
            result = _try_routing_provider('openrouteservice', {'api_key': 'key'}, 40, -75, 41, -74)
            mock_route.assert_called_once()

    def test_graphhopper(self):
        """Should call _route_graphhopper for graphhopper."""
        with patch('core.services._route_graphhopper') as mock_route:
            mock_route.return_value = {'success': True, 'distance_miles': 100}
            result = _try_routing_provider('graphhopper', {'api_key': 'key'}, 40, -75, 41, -74)
            mock_route.assert_called_once()

    def test_osrm_public(self):
        """Should call _route_osrm for osrm_public."""
        with patch('core.services._route_osrm') as mock_route:
            mock_route.return_value = {'success': True, 'distance_miles': 100}
            result = _try_routing_provider('osrm_public', {'url': 'http://test'}, 40, -75, 41, -74)
            mock_route.assert_called_once()

    def test_http_error_retry(self):
        """Should retry on HTTP error."""
        with patch('core.services._route_osrm') as mock_route:
            mock_route.side_effect = [httpx.HTTPError("Error"), {'success': True, 'distance_miles': 100}]
            result = _try_routing_provider('osrm_public', {'url': 'http://test'}, 40, -75, 41, -74)
            self.assertTrue(result['success'])
            self.assertEqual(mock_route.call_count, 2)

    def test_http_error_final_failure(self):
        """Should return failure after retries exhausted (line 257)."""
        # Use invalid provider name to make try block not return, hitting line 257
        result = _try_routing_provider('invalid_provider', {'url': 'http://test'}, 40, -75, 41, -74)
        self.assertFalse(result['success'])
        self.assertIn('failed after retries', result['error'])

    def test_try_routing_provider_http_error_second_attempt(self):
        """Should handle HTTPError on second attempt (line 254)."""
        with patch('core.services._route_osrm') as mock_route:
            # First attempt: HTTPError -> continue to retry
            # Second attempt: HTTPError -> return from line 254
            mock_route.side_effect = [
                httpx.HTTPError("First HTTP error"),
                httpx.HTTPError("Second HTTP error")
            ]
            result = _try_routing_provider('osrm_public', {'url': 'http://test'}, 40, -75, 41, -74)
            self.assertFalse(result['success'])
            self.assertIn('http error', result['error'].lower())
            self.assertIn('second http error', result['error'].lower())
            self.assertEqual(mock_route.call_count, 2)

    def test_exception_no_retry(self):
        """Should not retry on generic exception."""
        with patch('core.services._route_osrm') as mock_route:
            mock_route.side_effect = Exception("Error")
            result = _try_routing_provider('osrm_public', {'url': 'http://test'}, 40, -75, 41, -74)
            self.assertFalse(result['success'])


class TestRouteOSRM(TestCase):
    """Test _route_osrm function."""

    @patch('core.services.httpx.Client')
    def test_route_osrm_success(self, mock_client_class):
        """Should route successfully with OSRM."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'code': 'Ok',
            'routes': [{
                'distance': 160934,  # 100 miles in meters
                'duration': 6000,    # 100 minutes in seconds
                'geometry': {'type': 'LineString', 'coordinates': []}
            }]
        }
        mock_client.get.return_value = mock_response

        result = _route_osrm('https://router.project-osrm.org', 41.8781, -87.6298, 32.7767, -96.7970)

        self.assertTrue(result['success'])
        self.assertAlmostEqual(result['distance_miles'], 100.0, places=1)
        self.assertAlmostEqual(result['duration_minutes'], 100.0, places=1)

    @patch('core.services.httpx.Client')
    def test_route_osrm_no_routes(self, mock_client_class):
        """Should handle no routes from OSRM."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'code': 'Ok', 'routes': []}
        mock_client.get.return_value = mock_response

        result = _route_osrm('https://router.project-osrm.org', 41.8781, -87.6298, 32.7767, -96.7970)

        self.assertFalse(result['success'])
        self.assertIn('no routes', result['error'].lower())


class TestRouteORS(TestCase):
    """Test _route_ors function."""

    @patch('core.services.httpx.Client')
    def test_route_ors_success_geojson(self, mock_client_class):
        """Should route successfully with ORS returning GeoJSON."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'routes': [{
                'distance': 160934,
                'duration': 6000,
                'geometry': {'type': 'LineString', 'coordinates': [[-87.6, 41.8], [-96.8, 32.7]]}
            }]
        }
        mock_client.post.return_value = mock_response

        result = _route_ors('test-key', 41.8781, -87.6298, 32.7767, -96.7970)

        self.assertTrue(result['success'])
        self.assertAlmostEqual(result['distance_miles'], 100.0, places=1)

    @patch('core.services.httpx.Client')
    def test_route_ors_success_polyline(self, mock_client_class):
        """Should route successfully with ORS returning encoded polyline."""
        import polyline
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        # ORS returns encoded polyline when geometry_format not specified
        encoded = polyline.encode([(41.8781, -87.6298), (32.7767, -96.7970)])
        mock_response.json.return_value = {
            'routes': [{
                'distance': 160934,
                'duration': 6000,
                'geometry': encoded
            }]
        }
        mock_client.post.return_value = mock_response

        result = _route_ors('test-key', 41.8781, -87.6298, 32.7767, -96.7970)

        self.assertTrue(result['success'])
        self.assertAlmostEqual(result['distance_miles'], 100.0, places=1)

    @patch('core.services.httpx.Client')
    def test_route_ors_no_routes(self, mock_client_class):
        """Should handle no routes from ORS."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'routes': []}
        mock_client.post.return_value = mock_response

        result = _route_ors('test-key', 41.8781, -87.6298, 32.7767, -96.7970)

        self.assertFalse(result['success'])


class TestRouteGraphHopper(TestCase):
    """Test _route_graphhopper function."""

    @patch('core.services.httpx.Client')
    def test_route_gh_success(self, mock_client_class):
        """Should route successfully with GraphHopper."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'paths': [{
                'distance': 160934,
                'time': 6000000,  # ms
                'points': {'type': 'LineString', 'coordinates': [[-87.6, 41.8], [-96.8, 32.7]]}
            }]
        }
        mock_client.get.return_value = mock_response

        result = _route_graphhopper('test-key', 41.8781, -87.6298, 32.7767, -96.7970)

        self.assertTrue(result['success'])
        self.assertAlmostEqual(result['distance_miles'], 100.0, places=1)
        self.assertAlmostEqual(result['duration_minutes'], 100.0, places=1)

    @patch('core.services.httpx.Client')
    def test_route_gh_no_paths(self, mock_client_class):
        """Should handle no paths from GraphHopper."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'paths': []}
        mock_client.get.return_value = mock_response

        result = _route_graphhopper('test-key', 41.8781, -87.6298, 32.7767, -96.7970)

        self.assertFalse(result['success'])

    @patch('core.services.httpx.Client')
    def test_route_graphhopper_with_encoded_geometry(self, mock_client_class):
        """Should handle encoded polyline geometry in GraphHopper response (lines 336-337)."""
        import polyline
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Create encoded polyline
        encoded = polyline.encode([(41.8781, -87.6298), (32.7767, -96.7970)])
        mock_response.json.return_value = {
            'paths': [{
                'points': encoded,
                'distance': 160934,
                'time': 6000000
            }]
        }
        mock_client.get.return_value = mock_response

        result = _route_graphhopper('test-key', 41.8781, -87.6298, 32.7767, -96.7970)

        self.assertTrue(result['success'])
        self.assertAlmostEqual(result['distance_miles'], 100.0, places=1)
        self.assertIn('geometry', result)

    @patch('core.services.httpx.Client')
    def test_route_graphhopper_with_geojson_geometry(self, mock_client_class):
        """Should handle GeoJSON geometry directly (bypassing polyline decode)."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'paths': [{
                'points': {
                    'type': 'LineString',
                    'coordinates': [[-87.6, 41.8], [-96.8, 32.7]]
                },
                'distance': 160934,
                'time': 6000000
            }]
        }
        mock_client.get.return_value = mock_response

        result = _route_graphhopper('test-key', 41.8781, -87.6298, 32.7767, -96.7970)

        self.assertTrue(result['success'])
        self.assertEqual(result['geometry']['coordinates'], [[-87.6, 41.8], [-96.8, 32.7]])


class TestRecordProviderSuccess(TestCase):
    """Test _record_provider_success function."""

    def test_record_osrm_local(self):
        OSRM_CIRCUIT_BREAKER.failures = 2
        _record_provider_success('osrm_local')
        self.assertEqual(OSRM_CIRCUIT_BREAKER.failures, 0)

    def test_record_ors(self):
        ORS_CIRCUIT_BREAKER.failures = 2
        _record_provider_success('openrouteservice')
        self.assertEqual(ORS_CIRCUIT_BREAKER.failures, 0)

    def test_record_gh(self):
        GRAPHHOPPER_CIRCUIT_BREAKER.failures = 2
        _record_provider_success('graphhopper')
        self.assertEqual(GRAPHHOPPER_CIRCUIT_BREAKER.failures, 0)

    def test_record_osrm_public(self):
        OSRM_CIRCUIT_BREAKER.failures = 2
        _record_provider_success('osrm_public')
        self.assertEqual(OSRM_CIRCUIT_BREAKER.failures, 0)


class TestGetDrivingRoute(TestCase):
    """Test get_driving_route function."""

    def setUp(self):
        RouteCache.objects.all().delete()
        OSRM_CIRCUIT_BREAKER.failures = 0
        OSRM_CIRCUIT_BREAKER.open = False
        ORS_CIRCUIT_BREAKER.failures = 0
        ORS_CIRCUIT_BREAKER.open = False
        GRAPHHOPPER_CIRCUIT_BREAKER.failures = 0
        GRAPHHOPPER_CIRCUIT_BREAKER.open = False

    @override_settings(
        OSRM_SELF_HOSTED_URL='',
        OPENROUTESERVICE_API_KEY='',
        GRAPHHOPPER_API_KEY='',
        OSRM_PUBLIC_URL='https://router.project-osrm.org'
    )
    @patch('core.services._try_routing_provider')
    def test_route_cache_hit(self, mock_try):
        """Should return cached route if available."""
        route_hash = 'testhash' + '0' * 58
        RouteCache.objects.create(
            route_hash=route_hash,
            start_lat=41.8781, start_lon=-87.6298,
            finish_lat=32.7767, finish_lon=-96.7970,
            distance_miles=925.4,
            duration_minutes=840.0,
            geometry_geojson={'type': 'LineString', 'coordinates': []},
            provider='osrm_public'
        )

        with patch('core.services.hashlib.sha256') as mock_hash:
            mock_hash.return_value.hexdigest.return_value = route_hash
            result = get_driving_route(41.8781, -87.6298, 32.7767, -96.7970)

        self.assertTrue(result['success'])
        self.assertTrue(result['cached'])
        mock_try.assert_not_called()

    @override_settings(
        OSRM_SELF_HOSTED_URL='',
        OPENROUTESERVICE_API_KEY='',
        GRAPHHOPPER_API_KEY='',
        OSRM_PUBLIC_URL='https://router.project-osrm.org'
    )
    @patch('core.services._try_routing_provider')
    def test_route_circuit_breaker_open(self, mock_try):
        """Should skip provider when circuit breaker open."""
        OSRM_CIRCUIT_BREAKER.open = True
        OSRM_CIRCUIT_BREAKER.last_failure = time.time()

        with patch('core.services._get_routing_providers') as mock_providers:
            mock_providers.return_value = [
                ('osrm_public', {'url': 'https://router.project-osrm.org'})
            ]
            # Don't let _try_routing_provider be called
            mock_try.return_value = {'success': False, 'error': 'should not be called'}
            result = get_driving_route(41.8781, -87.6298, 32.7767, -96.7970)

        self.assertFalse(result['success'])
        self.assertIn('unavailable', result['error'].lower())
        # Should not have called _try_routing_provider since circuit breaker is open
        mock_try.assert_not_called()

    @override_settings(
        OSRM_SELF_HOSTED_URL='',
        OPENROUTESERVICE_API_KEY='',
        GRAPHHOPPER_API_KEY='',
        OSRM_PUBLIC_URL='https://router.project-osrm.org'
    )
    @patch('core.services._try_routing_provider')
    def test_route_all_providers_fail(self, mock_try):
        """Should return error when all providers fail."""
        mock_try.return_value = {'success': False, 'error': 'Provider failed'}

        result = get_driving_route(41.8781, -87.6298, 32.7767, -96.7970)

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'All routing providers unavailable')

    @override_settings(
        OSRM_SELF_HOSTED_URL='',
        OPENROUTESERVICE_API_KEY='',
        GRAPHHOPPER_API_KEY='',
        OSRM_PUBLIC_URL='https://router.project-osrm.org'
    )
    @patch('core.services._get_routing_providers')
    def test_route_ors_circuit_breaker_open(self, mock_providers):
        """Should skip ORS when circuit breaker open (lines 182-183)."""
        # Set ORS circuit breaker to open
        ORS_CIRCUIT_BREAKER.open = True
        ORS_CIRCUIT_BREAKER.last_failure = time.time()

        # Mock providers to return ORS first, then OSRM public
        mock_providers.return_value = [
            ('openrouteservice', {'api_key': 'test-key'}),
            ('osrm_public', {'url': 'https://router.project-osrm.org'})
        ]

        # Mock _try_routing_provider to return success for OSRM (second provider)
        with patch('core.services._try_routing_provider') as mock_try:
            mock_try.return_value = {
                'success': True,
                'distance_miles': 100.0,
                'duration_minutes': 100.0,
                'geometry': {'type': 'LineString', 'coordinates': []}
            }

            result = get_driving_route(41.8781, -87.6298, 32.7767, -96.7970)

            # Should have skipped ORS due to circuit breaker and tried OSRM public
            self.assertTrue(result['success'])
            # Verify ORS was attempted but skipped (call count should be 1 for OSRM public)
            mock_try.assert_called_once()
            args, kwargs = mock_try.call_args
            self.assertEqual(args[0], 'osrm_public')  # Provider name

    @override_settings(
        OSRM_SELF_HOSTED_URL='',
        OPENROUTESERVICE_API_KEY='',
        GRAPHHOPPER_API_KEY='',
        OSRM_PUBLIC_URL='https://router.project-osrm.org'
    )
    @patch('core.services._get_routing_providers')
    def test_route_graphhopper_circuit_breaker_open(self, mock_providers):
        """Should skip GraphHopper when circuit breaker open (lines 185-186)."""
        # Set GraphHopper circuit breaker to open
        GRAPHHOPPER_CIRCUIT_BREAKER.open = True
        GRAPHHOPPER_CIRCUIT_BREAKER.last_failure = time.time()

        # Mock providers to return GraphHopper first, then OSRM public
        mock_providers.return_value = [
            ('graphhopper', {'api_key': 'test-key'}),
            ('osrm_public', {'url': 'https://router.project-osrm.org'})
        ]

        # Mock _try_routing_provider to return success for OSRM (second provider)
        with patch('core.services._try_routing_provider') as mock_try:
            mock_try.return_value = {
                'success': True,
                'distance_miles': 100.0,
                'duration_minutes': 100.0,
                'geometry': {'type': 'LineString', 'coordinates': []}
            }

            result = get_driving_route(41.8781, -87.6298, 32.7767, -96.7970)

            # Should have skipped GraphHopper due to circuit breaker and tried OSRM public
            self.assertTrue(result['success'])
            # Verify GraphHopper was attempted but skipped (call count should be 1 for OSRM public)
            mock_try.assert_called_once()
            args, kwargs = mock_try.call_args
            self.assertEqual(args[0], 'osrm_public')  # Provider name


class TestCalculateRoutePlan(TestCase):
    """Test calculate_route_plan function."""

    def setUp(self):
        Station.objects.all().delete()
        RoutePlan.objects.all().delete()
        RouteStop.objects.all().delete()

    @patch('core.services.geocode_location')
    @patch('core.services.get_driving_route')
    @patch('core.services.get_candidate_stations')
    @patch('core.services.optimize_fuel_stops')
    def test_plan_success(self, mock_optimize, mock_candidates, mock_route, mock_geo):
        """Should create route plan successfully."""
        mock_geo.side_effect = [
            {'success': True, 'lat': 41.8781, 'lon': -87.6298},
            {'success': True, 'lat': 32.7767, 'lon': -96.7970}
        ]
        mock_route.return_value = {
            'success': True,
            'distance_miles': 925.4,
            'duration_minutes': 840.0,
            'geometry': {'type': 'LineString', 'coordinates': []}
        }
        mock_candidates.return_value = []
        mock_optimize.return_value = {
            'stops': [],
            'total_gallons': 0.0,
            'total_cost': 0.0,
            'warnings': []
        }

        result = calculate_route_plan('Chicago, IL', 'Dallas, TX')

        self.assertTrue(result['success'])
        self.assertIn('plan_id', result)
        self.assertEqual(RoutePlan.objects.count(), 1)

    @patch('core.services.geocode_location')
    def test_plan_start_geocode_failure(self, mock_geo):
        """Should fail if start geocode fails."""
        mock_geo.return_value = {'success': False, 'error': 'Location not found'}

        result = calculate_route_plan('Invalid', 'Dallas, TX')

        self.assertFalse(result['success'])
        self.assertIn('geocode', result['error'].lower())

    @patch('core.services.geocode_location')
    @patch('core.services.get_driving_route')
    def test_plan_route_failure(self, mock_route, mock_geo):
        """Should fail if routing fails."""
        mock_geo.side_effect = [
            {'success': True, 'lat': 41.8781, 'lon': -87.6298},
            {'success': True, 'lat': 32.7767, 'lon': -96.7970}
        ]
        mock_route.return_value = {'success': False, 'error': 'No route'}

        result = calculate_route_plan('Chicago, IL', 'Dallas, TX')

        self.assertFalse(result['success'])
        self.assertIn('route', result['error'].lower())

    @patch('core.services.geocode_location')
    @patch('core.services.get_driving_route')
    @patch('core.services.get_candidate_stations')
    @patch('core.services.optimize_fuel_stops')
    def test_plan_with_cached_route(self, mock_optimize, mock_candidates, mock_route, mock_geo):
        """Should include cache info in response."""
        mock_geo.side_effect = [
            {'success': True, 'lat': 41.8781, 'lon': -87.6298, 'cached': True},
            {'success': True, 'lat': 32.7767, 'lon': -96.7970, 'cached': False}
        ]
        mock_route.return_value = {
            'success': True,
            'distance_miles': 925.4,
            'duration_minutes': 840.0,
            'geometry': {'type': 'LineString', 'coordinates': []},
            'cached': True
        }
        mock_candidates.return_value = []
        mock_optimize.return_value = {
            'stops': [],
            'total_gallons': 0.0,
            'total_cost': 0.0,
            'warnings': []
        }

        result = calculate_route_plan('Chicago, IL', 'Dallas, TX')

        self.assertTrue(result['cache']['route_cached'])
        self.assertTrue(result['cache']['geocode_cached'])

    @patch('core.services.geocode_location')
    @patch('core.services.get_driving_route')
    @patch('core.services.get_candidate_stations')
    @patch('core.services.optimize_fuel_stops')
    def test_plan_finish_geocode_failure(self, mock_optimize, mock_candidates, mock_route, mock_geo):
        """Should fail if finish geocode fails (line 369)."""
        mock_geo.side_effect = [
            {'success': True, 'lat': 41.8781, 'lon': -87.6298},
            {'success': False, 'error': 'Location not found'}
        ]
        mock_route.return_value = {
            'success': True,
            'distance_miles': 925.4,
            'duration_minutes': 840.0,
            'geometry': {'type': 'LineString', 'coordinates': []}
        }
        mock_candidates.return_value = []
        mock_optimize.return_value = {
            'stops': [],
            'total_gallons': 0.0,
            'total_cost': 0.0,
            'warnings': []
        }

        result = calculate_route_plan('Chicago, IL', 'Invalid Location')

        self.assertFalse(result['success'])
        self.assertIn('geocode', result['error'].lower())
        self.assertIn('finish location', result['error'])

    @patch('core.services.geocode_location')
    @patch('core.services.get_driving_route')
    @patch('core.services.get_candidate_stations')
    @patch('core.services.optimize_fuel_stops')
    def test_plan_with_fuel_stops(self, mock_optimize, mock_candidates, mock_route, mock_geo):
        """Should create route plan with fuel stops (lines 400-401)."""
        mock_geo.side_effect = [
            {'success': True, 'lat': 41.8781, 'lon': -87.6298},
            {'success': True, 'lat': 32.7767, 'lon': -96.7970}
        ]
        mock_route.return_value = {
            'success': True,
            'distance_miles': 925.4,
            'duration_minutes': 840.0,
            'geometry': {'type': 'LineString', 'coordinates': []}
        }
        mock_candidates.return_value = []

        # Return a mock station for the stop
        from core.models import Station
        Station.objects.all().delete()
        station = Station.objects.create(
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

        mock_optimize.return_value = {
            'stops': [
                {'station_id': station.id, 'route_distance': 100.0, 'gallons_purchased': 10.0, 'cost_usd': 35.0}
            ],
            'total_gallons': 10.0,
            'total_cost': 35.0,
            'warnings': []
        }

        result = calculate_route_plan('Chicago, IL', 'Dallas, TX')

        self.assertTrue(result['success'])
        self.assertEqual(len(result['stops']), 1)
        self.assertEqual(RouteStop.objects.count(), 1)
        self.assertEqual(RouteStop.objects.first().station_id, station.id)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])