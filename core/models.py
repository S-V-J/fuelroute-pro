import uuid
from django.db import models
from django.contrib.auth.models import User

class VehicleProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vehicle_profiles')
    name = models.CharField(max_length=100, help_text="e.g., 'My Semi', 'Daily Driver'")
    mpg = models.FloatField(default=10.0, help_text="Miles per gallon")
    tank_capacity_gallons = models.FloatField(default=50.0, help_text="Fuel tank capacity in gallons")
    is_default = models.BooleanField(default=False, help_text="Set as default vehicle for this user")

    class Meta:
        verbose_name_plural = "Vehicle Profiles"

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def save(self, *args, **kwargs):
        # Ensure only one default vehicle per user
        if self.is_default:
            VehicleProfile.objects.filter(user=self.user, is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


class Station(models.Model):
    opis_id = models.IntegerField(db_index=True, help_text="Original OPIS Truckstop ID")
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.IntegerField(db_index=True, help_text="Used for physical deduplication")
    retail_price = models.DecimalField(max_digits=6, decimal_places=3, help_text="USD per gallon")
    
    latitude = models.FloatField(null=True, blank=True, db_index=True)
    longitude = models.FloatField(null=True, blank=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['state', 'latitude', 'longitude']),
        ]

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state}) - ${self.retail_price}"


class GeocodeCache(models.Model):
    query = models.CharField(max_length=500)
    normalized_query = models.CharField(max_length=500, db_index=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    provider = models.CharField(max_length=50, db_index=True)
    raw_response = models.JSONField(default=dict, blank=True)
    is_success = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['normalized_query', 'provider']),
        ]

    def __str__(self):
        return f"[{self.provider}] {self.query} -> {'Success' if self.is_success else 'Failed'}"


class RouteCache(models.Model):
    route_hash = models.CharField(max_length=64, unique=True, db_index=True)
    start_lat = models.FloatField()
    start_lon = models.FloatField()
    finish_lat = models.FloatField()
    finish_lon = models.FloatField()
    distance_miles = models.FloatField()
    duration_minutes = models.FloatField()
    geometry_geojson = models.JSONField(default=dict)
    provider = models.CharField(max_length=50, default='osrm_public')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Route {self.route_hash[:8]}... ({self.distance_miles:.1f} mi)"


class RoutePlan(models.Model):
    # Added user field to link plans to authenticated users (null=True allows legacy anonymous plans)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='route_plans')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    start_query = models.CharField(max_length=255)
    start_lat = models.FloatField()
    start_lon = models.FloatField()
    finish_query = models.CharField(max_length=255)
    finish_lat = models.FloatField()
    finish_lon = models.FloatField()
    
    distance_miles = models.FloatField()
    geometry = models.TextField(blank=True, help_text="Encoded polyline string or GeoJSON")
    
    assumptions = models.JSONField(default=dict)
    warnings = models.JSONField(default=list)
    
    total_fuel_gallons = models.FloatField()
    total_cost_usd = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Plan {self.id} ({self.start_query} to {self.finish_query})"


class RouteStop(models.Model):
    plan = models.ForeignKey(RoutePlan, related_name='stops', on_delete=models.CASCADE)
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField()
    
    distance_from_start_miles = models.FloatField()
    gallons_purchased = models.FloatField()
    cost_usd = models.DecimalField(max_digits=8, decimal_places=2)
    
    class Meta:
        ordering = ['sequence']

    def __str__(self):
        return f"Stop {self.sequence}: {self.station.name}"