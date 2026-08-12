import csv
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from django.db import connection, OperationalError
from django.conf import settings
from django.db.models import Sum
from django.core.cache import cache
import django
from datetime import datetime, timezone
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from .models import Station, RoutePlan
from .services import calculate_route_plan
from .serializers import StationSerializer

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        db_reachable = False
        station_count = 0
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_reachable = True
            station_count = Station.objects.count()
        except Exception:
            pass
        return Response({
            "status": "ok" if db_reachable else "degraded",
            "django_version": django.get_version(),
            "database_reachable": db_reachable,
            "fuel_station_count": station_count,
            "default_routing_provider": getattr(settings, "ROUTING_PROVIDER", "osrm_public"),
            "default_geocode_provider": getattr(settings, "GEOCODE_PROVIDER", "photon_census"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


class LivenessView(APIView):
    """Kubernetes liveness probe — returns 200 if the process is alive."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "alive"}, status=200)


class ReadinessView(APIView):
    """Kubernetes readiness probe — checks DB and cache are operational."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        checks = {}

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks["database"] = "ok"
        except OperationalError as e:
            checks["database"] = f"error: {str(e)}"
            return Response({"status": "not ready", "checks": checks}, status=503)
        except Exception as e:
            checks["database"] = f"error: {str(e)}"
            return Response({"status": "not ready", "checks": checks}, status=503)

        try:
            cache.set("_readiness_check", "ok", 10)
            if cache.get("_readiness_check") != "ok":
                checks["cache"] = "error: read/write mismatch"
                return Response({"status": "not ready", "checks": checks}, status=503)
            checks["cache"] = "ok"
        except Exception as e:
            checks["cache"] = f"error: {str(e)}"
            return Response({"status": "not ready", "checks": checks}, status=503)

        return Response({"status": "ready", "checks": checks}, status=200)

class StatsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        stats = cache.get('platform_stats')
        if not stats:
            station_count = Station.objects.count()
            total_plans = RoutePlan.objects.count()
            stats = {
                "station_count": station_count,
                "total_plans": total_plans,
                "avg_savings": "~15%",
                "avg_response_time": "< 2.0s"
            }
            cache.set('platform_stats', stats, 300)
        return Response(stats)

class PlanRouteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'plan'

    def post(self, request):
        start = request.data.get('start')
        finish = request.data.get('finish')
        if not start or not finish:
            return Response({"error": "Both 'start' and 'finish' locations are required."}, status=400)
            
        range_miles = float(request.data.get('range_miles', 500.0))
        mpg = float(request.data.get('mpg', 10.0))
        start_fuel_gallons = float(request.data.get('start_fuel_gallons', 0.0))
        station_buffer_miles = float(request.data.get('station_buffer_miles', 25.0))
        
        result = calculate_route_plan(
            start_query=start, finish_query=finish, range_miles=range_miles,
            mpg=mpg, start_fuel_gallons=start_fuel_gallons, station_buffer_miles=station_buffer_miles,
            user=request.user if request.user.is_authenticated else None
        )
        if not result['success']:
            return Response({"error": result['error']}, status=400)
        return Response(result, status=200)

class PlanRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, plan_id):
        try:
            plan = RoutePlan.objects.get(id=plan_id)
            stops_data = []
            for stop in plan.stops.all().order_by('sequence'):
                stops_data.append({
                    'station_id': stop.station.id,
                    'station_name': stop.station.name,
                    'price_per_gallon': float(stop.station.retail_price),
                    'gallons_purchased': stop.gallons_purchased,
                    'cost_usd': float(stop.cost_usd),
                    'route_distance': stop.distance_from_start_miles
                })
            
            return Response({
                'success': True,
                'plan_id': str(plan.id),
                'start': {'query': plan.start_query, 'lat': plan.start_lat, 'lon': plan.start_lon},
                'finish': {'query': plan.finish_query, 'lat': plan.finish_lat, 'lon': plan.finish_lon},
                'route': {'distance_miles': plan.distance_miles, 'geometry': plan.geometry},
                'assumptions': plan.assumptions,
                'stops': stops_data,
                'totals': {
                    'fuel_gallons_purchased': plan.total_fuel_gallons,
                    'fuel_cost_usd': float(plan.total_cost_usd),
                    'stop_count': len(stops_data)
                },
                'warnings': plan.warnings,
                'cache': {'route_cached': True, 'geocode_cached': True}
            }, status=200)
        except RoutePlan.DoesNotExist:
            return Response({"error": "Plan not found."}, status=404)

class StationListView(generics.ListAPIView):
    queryset = Station.objects.filter(latitude__isnull=False, longitude__isnull=False).order_by('state', 'city')
    serializer_class = StationSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = super().get_queryset()
        state = self.request.query_params.get('state')
        city = self.request.query_params.get('city')
        max_price = self.request.query_params.get('max_price')
        
        if state:
            qs = qs.filter(state__iexact=state)
        if city:
            qs = qs.filter(city__icontains=city)
        if max_price:
            qs = qs.filter(retail_price__lte=float(max_price))
        return qs

class ProviderMetadataView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({
            "routing_provider": getattr(settings, "ROUTING_PROVIDER", "osrm_public"),
            "geocode_provider": getattr(settings, "GEOCODE_PROVIDER", "photon_census"),
            "defaults": {
                "range_miles": getattr(settings, "DEFAULT_RANGE_MILES", 500),
                "mpg": getattr(settings, "DEFAULT_MPG", 10),
                "station_buffer_miles": getattr(settings, "STATION_BUFFER_MILES", 25)
            },
            "api_keys_configured": {
                "openrouteservice": bool(getattr(settings, "OPENROUTESERVICE_API_KEY", "")),
                "graphhopper": bool(getattr(settings, "GRAPHHOPPER_API_KEY", ""))
            }
        })

class HomeView(View):
    def get(self, request):
        return render(request, 'core/home.html')

    def post(self, request):
        start = request.POST.get('start', '').strip()
        finish = request.POST.get('finish', '').strip()
        
        if not start or not finish:
            return render(request, 'core/_error.html', {'error': 'Both start and finish locations are required.'})
            
        try:
            range_miles = float(request.POST.get('range_miles', 500.0))
            mpg = float(request.POST.get('mpg', 10.0))
            start_fuel_gallons = float(request.POST.get('start_fuel_gallons', 0.0))
            station_buffer_miles = float(request.POST.get('station_buffer_miles', 25.0))
        except ValueError:
            return render(request, 'core/_error.html', {'error': 'Invalid numeric input for vehicle settings.'})
            
        result = calculate_route_plan(
            start_query=start,
            finish_query=finish,
            range_miles=range_miles,
            mpg=mpg,
            start_fuel_gallons=start_fuel_gallons,
            station_buffer_miles=station_buffer_miles,
            user=request.user if request.user.is_authenticated else None
        )
        
        if not result['success']:
            return render(request, 'core/_error.html', {'error': result.get('error', 'An unknown error occurred.')})
            
        return render(request, 'core/_results.html', {'result': result})


class CustomRegisterView(View):
    def get(self, request):
        form = UserCreationForm()
        return render(request, 'core/register.html', {'form': form})

    def post(self, request):
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
        return render(request, 'core/register.html', {'form': form})


@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        plans = RoutePlan.objects.filter(user=request.user).order_by('-created_at')
        recent_plans = plans[:5]
        
        total_routes = plans.count()
        agg_gallons = plans.aggregate(Sum('total_fuel_gallons'))['total_fuel_gallons__sum']
        total_gallons = float(agg_gallons) if agg_gallons is not None else 0.0
        
        agg_cost = plans.aggregate(Sum('total_cost_usd'))['total_cost_usd__sum']
        total_cost = float(agg_cost) if agg_cost is not None else 0.0
        estimated_savings = round(total_cost * 0.15, 2)
        
        default_vehicle = request.user.vehicle_profiles.filter(is_default=True).first()
        if not default_vehicle:
            default_vehicle = request.user.vehicle_profiles.first()

        context = {
            'total_routes': total_routes,
            'total_gallons': round(total_gallons, 2),
            'total_cost': round(total_cost, 2),
            'estimated_savings': estimated_savings,
            'recent_plans': recent_plans,
            'default_vehicle': default_vehicle,
        }
        return render(request, 'core/dashboard.html', context)


class AboutView(View):
    def get(self, request):
        return render(request, 'core/about.html')


class SupportView(View):
    def get(self, request):
        return render(request, 'core/support.html')


@login_required
def export_plan_csv(request, plan_id):
    plan = get_object_or_404(RoutePlan, id=plan_id)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="route_{plan.id}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Stop', 'Station Name', 'Mile Marker', 'Gallons', 'Price/Gal', 'Total Cost'])
    for stop in plan.stops.all().order_by('sequence'):
        writer.writerow([
            stop.sequence,
            stop.station.name,
            stop.distance_from_start_miles,
            stop.gallons_purchased,
            float(stop.station.retail_price),
            float(stop.cost_usd)
        ])
    return response


@login_required
def export_plan_geojson(request, plan_id):
    plan = get_object_or_404(RoutePlan, id=plan_id)
    response = HttpResponse(plan.geometry, content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="route_{plan.id}.geojson"'
    return response