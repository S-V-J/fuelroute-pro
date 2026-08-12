from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import (
    HealthCheckView, LivenessView, ReadinessView, StatsView, PlanRouteView, PlanRetrieveView,
    StationListView, ProviderMetadataView, HomeView,
    CustomRegisterView, DashboardView, AboutView, SupportView,
    export_plan_csv, export_plan_geojson
)

urlpatterns = [
    # UI Routes
    path('', HomeView.as_view(), name='home'),
    path('about/', AboutView.as_view(), name='about'),
    path('support/', SupportView.as_view(), name='support'),
    path('login/', LoginView.as_view(template_name='core/login.html', redirect_authenticated_user=True), name='login'),
    path('register/', CustomRegisterView.as_view(), name='register'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('dashboard/export/csv/<uuid:plan_id>/', export_plan_csv, name='export_plan_csv'),
    path('dashboard/export/geojson/<uuid:plan_id>/', export_plan_geojson, name='export_plan_geojson'),

    # API Routes
    path('api/v1/health/', HealthCheckView.as_view(), name='health-check'),
    path('health/live/', LivenessView.as_view(), name='health-live'),
    path('health/ready/', ReadinessView.as_view(), name='health-ready'),
    path('api/v1/stats/', StatsView.as_view(), name='platform-stats'),
    path('api/v1/plan/', PlanRouteView.as_view(), name='plan-route'),
    path('api/v1/plan/<uuid:plan_id>/', PlanRetrieveView.as_view(), name='plan-retrieve'),
    path('api/v1/stations/', StationListView.as_view(), name='station-list'),
    path('api/v1/providers/', ProviderMetadataView.as_view(), name='provider-metadata'),
]
