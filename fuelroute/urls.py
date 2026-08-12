"""
URL configuration for fuelroute project.
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Mount core URLs (including HomeView at root '') at the root level
    path('', include('core.urls')),

    # OpenAPI 3 Schema and Swagger UI Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Prometheus metrics
    path('', include('django_prometheus.urls')),
]
