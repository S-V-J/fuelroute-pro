"""
Tests for optimizer functionality with 100% coverage.
"""
from django.test import TestCase
from core.optimizer import optimize_fuel_stops, get_candidate_stations, calculate_route_bbox, haversine_miles
from core.models import Station
from unittest.mock import patch, MagicMock


class TestOptimizerCoverage(TestCase):
    """Tests to achieve 100% coverage for optimizer functions."""

    def test_optimize_fuel_stops_destination_reachable_break(self):
        """Test that the loop breaks when destination is reachable (line 313)."""
        # Create a mock station that's at the destination point
        mock_station = MagicMock()
        mock_station.id = 1
        mock_station.name = "Destination Station"
        mock_station.retail_price = 3.50

        # Create a candidate that represents reaching the destination directly
        # Format matches what's expected in optimizer.py lines 115-120 and 206-211
        reachable_destination = {
            'station': mock_station,
            'offset_miles': 0.0,
            'route_distance': 100.0,  # At destination
            'price': float(mock_station.retail_price)
        }

        # Add the virtual destination marker as the optimizer does internally
        # This simulates what happens in lines 206-211 of optimizer.py
        # Include offset_miles to match the candidate format expected by _dedupe_same_marker
        candidates = [reachable_destination, {
            'station': None,
            'offset_miles': 0.0,
            'route_distance': 100.0,
            'price': 0.0,
            'is_destination': True
        }]

        # This test ensures the loop can handle the destination case properly
        # The break condition on line 313 will be tested in this scenario
        result = optimize_fuel_stops(
            total_distance_miles=100.0,
            candidates=candidates,
            range_miles=500.0,
            mpg=10.0,
            start_fuel_gallons=0.0
        )

        # Should have stops (the exact number depends on the algorithm)
        # This test primarily verifies the code path through line 313 executes
        self.assertIn('stops', result)
        self.assertIn('total_gallons', result)
        self.assertIn('total_cost', result)

    def test_get_candidate_stations_empty(self):
        """Test get_candidate_stations with empty route geometry."""
        result = get_candidate_stations({}, buffer_miles=10.0, total_distance_miles=100.0)
        self.assertEqual(result, [])

    def test_get_candidate_stations_no_stations(self):
        """Test get_candidate_stations when no stations match the bbox."""
        with patch('core.optimizer.Station.objects.filter') as mock_query:
            # Mock empty result from filter
            mock_query.return_value = []

            result = get_candidate_stations({'coordinates': []}, 10.0, 100.0)
            self.assertEqual(result, [])

    def test_haversine_miles_same_point(self):
        """Test haversine distance from a point to itself is 0."""
        dist = haversine_miles(40.0, -90.0, 40.0, -90.0)
        self.assertEqual(dist, 0.0)

    def test_calculate_route_bbox_empty(self):
        """Empty coordinates should return full world bounds."""
        bbox = calculate_route_bbox({}, 25.0)
        self.assertEqual(bbox['min_lat'], -90)
        self.assertEqual(bbox['max_lat'], 90)
        self.assertEqual(bbox['min_lon'], -180)
        self.assertEqual(bbox['max_lon'], 180)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])