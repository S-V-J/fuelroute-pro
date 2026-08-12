"""
Tests for the fuel optimization engine.
"""
import pytest
from unittest.mock import Mock, patch
from core.optimizer import optimize_fuel_stops, haversine_miles


class MockStation:
    """Mock station object for testing."""
    def __init__(self, id, name, price, lat, lon):
        self.id = id
        self.name = name
        self.retail_price = price
        self.latitude = lat
        self.longitude = lon


def make_candidates(stations, distances):
    """Helper to create candidate list from stations and distances."""
    return [
        {'station': s, 'route_distance': d, 'offset_miles': 0.1, 'price': float(s.retail_price)}
        for s, d in zip(stations, distances)
    ]


class TestHaversine:
    """Test haversine distance calculation."""

    def test_same_point(self):
        """Distance from a point to itself should be 0."""
        dist = haversine_miles(40.0, -90.0, 40.0, -90.0)
        assert dist == 0.0

    def test_known_distance(self):
        """Test known distance: 1 degree longitude at 40N ≈ 53 miles."""
        dist = haversine_miles(40.0, -90.0, 40.0, -89.0)
        assert 52.0 < dist < 54.0

    def test_north_south(self):
        """Test north-south distance: 1 degree latitude ≈ 69 miles."""
        dist = haversine_miles(40.0, -90.0, 41.0, -90.0)
        assert 68.0 < dist < 70.0


class TestOptimizerShortRoutes:
    """Test optimizer with short routes that need no intermediate stops."""

    def test_short_route_with_start_fuel(self):
        """Route within range with starting fuel should need no stops."""
        stations = [
            MockStation(1, 'Start', 3.50, 40.0, -90.0),
            MockStation(2, 'End', 3.00, 40.0, -86.2),
        ]
        candidates = make_candidates(stations, [0.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=20.0  # 200 miles range
        )

        assert result['total_gallons'] == 0.0
        assert result['total_cost'] == 0.0
        assert len(result['stops']) == 0
        assert len(result['warnings']) == 0

    def test_short_route_zero_start_fuel(self):
        """Short route with 0 start fuel should buy at virtual start."""
        stations = [
            MockStation(1, 'Start Station', 3.50, 40.0, -90.0),
            MockStation(2, 'End Station', 3.00, 40.0, -86.2),
        ]
        candidates = make_candidates(stations, [0.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )

        assert result['total_gallons'] == 20.0
        assert result['total_cost'] == 70.0  # 20 * 3.50
        assert len(result['stops']) == 1
        assert result['stops'][0]['station_name'] == 'Start Station'
        assert result['stops'][0]['gallons_purchased'] == 20.0


class TestOptimizerMediumRoutes:
    """Test optimizer with routes requiring one stop."""

    def test_one_stop_cheaper_ahead(self):
        """Should buy minimal at expensive station to reach cheaper one."""
        stations = [
            MockStation(1, 'Expensive', 4.00, 40.0, -90.0),
            MockStation(2, 'Cheap', 2.00, 40.0, -88.1),   # ~100 miles
            MockStation(3, 'End', 3.00, 40.0, -86.2),     # ~200 miles
        ]
        candidates = make_candidates(stations, [0.0, 100.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )

        # Virtual start at Cheap (100 miles, $2.00)
        # Buy 10 gal at $2.00 = $20 to reach Cheap
        # From Cheap, destination is 100 miles, need 10 gal at $2.00 = $20
        # Total: 20 gal, $40
        assert result['total_gallons'] == 20.0
        assert result['total_cost'] == 40.0
        assert len(result['stops']) == 2

    def test_one_stop_no_cheaper_ahead(self):
        """Should fill tank when no cheaper station ahead."""
        stations = [
            MockStation(1, 'Cheap', 2.00, 40.0, -90.0),
            MockStation(2, 'Expensive', 4.00, 40.0, -88.1),  # ~100 miles
            MockStation(3, 'End', 3.00, 40.0, -86.2),        # ~200 miles
        ]
        candidates = make_candidates(stations, [0.0, 100.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )

        # Virtual start at Cheap (0 miles, $2.00) - cheapest and closest
        # Can reach destination directly (200 < 500 range)
        # Buy 20 gal at $2.00 = $40
        assert result['total_gallons'] == 20.0
        assert result['total_cost'] == 40.0
        assert len(result['stops']) == 1


class TestOptimizerLongRoutes:
    """Test optimizer with routes requiring multiple stops."""

    def test_multiple_stops_600_miles(self):
        """600 mile route with 500 mile range needs at least one stop."""
        stations = [
            MockStation(1, 'Start', 3.50, 40.0, -90.0),
            MockStation(2, 'Station B', 3.00, 40.0, -87.2),   # ~150 miles
            MockStation(3, 'Station C', 2.50, 40.0, -84.4),   # ~300 miles - cheapest
            MockStation(4, 'Station D', 2.80, 40.0, -81.6),   # ~450 miles
            MockStation(5, 'End', 3.20, 40.0, -78.8),         # ~600 miles
        ]
        candidates = make_candidates(stations, [0.0, 150.0, 300.0, 450.0, 600.0])

        result = optimize_fuel_stops(
            total_distance_miles=600.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )

        # Need 60 gallons total for 600 miles
        assert result['total_gallons'] == 60.0
        # Virtual start at Station C (300 miles, $2.50) - cheapest within 500 miles
        # Buy 30 gal at $2.50 = $75 to reach Station C
        # From Station C, destination 300 miles away, buy 30 gal at $2.50 = $75
        # Total: $150
        assert result['total_cost'] == 150.0
        assert len(result['stops']) == 2

    def test_equal_prices_prefers_fewer_stops(self):
        """When prices are equal, should minimize stops."""
        stations = [
            MockStation(1, 'Start', 3.00, 40.0, -90.0),
            MockStation(2, 'Mid', 3.00, 40.0, -88.1),
            MockStation(3, 'End', 3.00, 40.0, -86.2),
        ]
        candidates = make_candidates(stations, [0.0, 100.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )

        # Virtual start at Start (0 miles, $3.00) - cheapest and closest
        # Can reach destination directly
        assert result['total_gallons'] == 20.0
        assert result['total_cost'] == 60.0
        assert len(result['stops']) == 1


class TestOptimizerEdgeCases:
    """Test optimizer edge cases and error handling."""

    def test_unreachable_gap(self):
        """Should warn when gap exceeds vehicle range."""
        stations = [
            MockStation(1, 'Start', 3.50, 40.0, -90.0),
            MockStation(2, 'Station B', 3.00, 40.0, -87.2),   # ~150 miles
            MockStation(3, 'Station C', 2.50, 40.0, -81.6),   # ~450 miles - 300 mile gap!
            MockStation(4, 'End', 3.20, 40.0, -78.8),         # ~600 miles
        ]
        candidates = make_candidates(stations, [0.0, 150.0, 450.0, 600.0])

        result = optimize_fuel_stops(
            total_distance_miles=600.0,
            candidates=candidates,
            range_miles=200.0,  # Can only go 200 miles
            mpg=10.0,
            start_fuel_gallons=0.0
        )

        assert len(result['warnings']) > 0
        assert 'Stranded' in result['warnings'][0]

    def test_no_stations_reachable(self):
        """Should warn when no stations within range of start."""
        stations = [
            MockStation(1, 'Far Station', 3.50, 40.0, -80.0),  # ~500+ miles away
        ]
        candidates = make_candidates(stations, [500.0])

        result = optimize_fuel_stops(
            total_distance_miles=100.0,
            candidates=candidates,
            range_miles=200.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )

        assert len(result['warnings']) > 0
        assert 'No fuel stations reachable' in result['warnings'][0]

    def test_start_fuel_sufficient(self):
        """Starting with enough fuel should need no stops."""
        stations = [
            MockStation(1, 'Start', 3.50, 40.0, -90.0),
            MockStation(2, 'End', 3.00, 40.0, -86.2),
        ]
        candidates = make_candidates(stations, [0.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=50.0  # Full tank = 500 miles
        )

        assert result['total_gallons'] == 0.0
        assert result['total_cost'] == 0.0
        assert len(result['stops']) == 0

    def test_start_fuel_partial(self):
        """Starting with partial fuel should optimize remaining journey."""
        stations = [
            MockStation(1, 'Start', 3.50, 40.0, -90.0),
            MockStation(2, 'Cheap', 2.50, 40.0, -88.1),   # ~100 miles
            MockStation(3, 'End', 3.00, 40.0, -86.2),     # ~200 miles
        ]
        candidates = make_candidates(stations, [0.0, 100.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=10.0  # 100 miles range
        )

        # Start with 10 gal (100 miles). Can reach Cheap at 100 miles with 0 fuel left.
        # From Cheap, destination 100 miles away, need 10 gal at $2.50 = $25
        assert result['total_gallons'] == 10.0
        assert result['total_cost'] == 25.0
        assert len(result['stops']) == 1
        assert result['stops'][0]['station_name'] == 'Cheap'

    def test_virtual_start_at_zero_distance(self):
        """Virtual start at distance 0 should not have '(Virtual Start)' suffix."""
        stations = [
            MockStation(1, 'Start Station', 3.50, 40.0, -90.0),
            MockStation(2, 'End Station', 3.00, 40.0, -86.2),
        ]
        candidates = make_candidates(stations, [0.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )

        assert result['stops'][0]['station_name'] == 'Start Station'
        assert '(Virtual Start)' not in result['stops'][0]['station_name']

    def test_virtual_start_at_distance(self):
        """Virtual start at distance > 0 should have '(Virtual Start)' suffix."""
        stations = [
            MockStation(1, 'Start Station', 3.50, 40.0, -90.0),
            MockStation(2, 'Cheaper Station', 2.50, 40.0, -88.1),  # ~100 miles
            MockStation(3, 'End Station', 3.00, 40.0, -86.2),
        ]
        candidates = make_candidates(stations, [0.0, 100.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )

        # Virtual start should be at Cheaper Station (100 miles)
        assert '(Virtual Start)' in result['stops'][0]['station_name']
        assert result['stops'][0]['route_distance'] == 100.0


class TestOptimizerWithStartFuel:
    """Test optimizer with various starting fuel amounts."""

    def test_start_fuel_reaches_cheaper(self):
        """Start fuel reaches a cheaper station."""
        stations = [
            MockStation(1, 'Start', 4.00, 40.0, -90.0),
            MockStation(2, 'Cheap', 2.00, 40.0, -88.1),   # ~100 miles
            MockStation(3, 'End', 3.00, 40.0, -86.2),     # ~200 miles
        ]
        candidates = make_candidates(stations, [0.0, 100.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=15.0  # 150 miles range
        )

        # Start with 15 gal. Can reach Cheap (100 miles) with 5 gal left.
        # Destination 100 miles from Cheap, need 10 gal. Have 5, need 5 more at $2.00 = $10
        assert result['total_gallons'] == 5.0
        assert result['total_cost'] == 10.0
        assert len(result['stops']) == 1
        assert result['stops'][0]['station_name'] == 'Cheap'

    def test_start_fuel_skip_expensive(self):
        """Start fuel allows skipping expensive first station."""
        stations = [
            MockStation(1, 'Expensive', 4.00, 40.0, -90.0),
            MockStation(2, 'Cheap', 2.00, 40.0, -88.1),   # ~100 miles
            MockStation(3, 'End', 3.00, 40.0, -86.2),     # ~200 miles
        ]
        candidates = make_candidates(stations, [0.0, 100.0, 200.0])

        result = optimize_fuel_stops(
            total_distance_miles=200.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=15.0  # 150 miles range - can reach Cheap
        )

        # Should NOT stop at Expensive (0 miles), should reach Cheap
        stop_names = [s['station_name'] for s in result['stops']]
        assert 'Expensive' not in stop_names
        assert 'Cheap' in stop_names


if __name__ == '__main__':
    pytest.main([__file__, '-v'])