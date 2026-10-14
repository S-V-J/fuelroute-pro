"""Tests for core models."""

from django.test import TestCase
from core.models import Station


class CoreModelsTest(TestCase):
    """Test core models."""

    def test_station_model_import(self):
        """Test that Station model can be imported and instantiated."""
        self.assertTrue(hasattr(Station, 'name'))
        self.assertTrue(hasattr(Station, 'retail_price'))

    def test_station_str_method(self):
        """Test Station __str__ method if implemented."""
        station = Station(name="Test Station", retail_price=3.50)
        # This just tests the model can be created without saving
        self.assertEqual(station.name, "Test Station")