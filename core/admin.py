from django.contrib import admin
from .models import Station, RoutePlan, RouteStop, GeocodeCache, RouteCache, VehicleProfile

@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'state', 'retail_price', 'rack_id', 'latitude', 'longitude')
    list_filter = ('state',)
    search_fields = ('name', 'city', 'address')

@admin.register(RoutePlan)
class RoutePlanAdmin(admin.ModelAdmin):
    list_display = ('user', 'id', 'start_query', 'finish_query', 'distance_miles', 'total_cost_usd', 'created_at')
    list_filter = ('user',)
    readonly_fields = ('id', 'created_at')

@admin.register(RouteStop)
class RouteStopAdmin(admin.ModelAdmin):
    list_display = ('plan', 'sequence', 'station', 'gallons_purchased', 'cost_usd')

@admin.register(VehicleProfile)
class VehicleProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'mpg', 'tank_capacity_gallons', 'is_default')
    list_filter = ('is_default',)
    search_fields = ('user__username', 'name')