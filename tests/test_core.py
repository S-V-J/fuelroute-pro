"""
Tests for core functionality.
"""

from django.test import TestCase
from core.models import Station


class CoreTests(TestCase):
    """Test core functionality."""

    def test_core_import(self):
        """Test that core models can be imported."""
        self.assertTrue(hasattr(Station, 'name'))
        self.assertTrue(hasattr(Station, 'retail_price'))

    def test_station_instantiation(self):
        """Test Station model instantiation."""
        station = Station(name="Test Station", retail_price=3.50)
        self.assertEqual(station.name, "Test Station")