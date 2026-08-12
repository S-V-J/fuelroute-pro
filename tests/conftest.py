"""
Pytest configuration for FuelRoute Pro tests.
"""
import pytest
import django
from django.conf import settings
import os

# Configure Django settings before importing any Django modules
def pytest_configure(config):
    """Configure Django for pytest."""
    if not settings.configured:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings.configure(
            DEBUG=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.admin',
                'django.contrib.auth',
                'django.contrib.contenttypes',
                'django.contrib.sessions',
                'django.contrib.messages',
                'django.contrib.staticfiles',
                'rest_framework',
                'drf_spectacular',
                'core',
            ],
            MIDDLEWARE=[
                'django.middleware.security.SecurityMiddleware',
                'django.contrib.sessions.middleware.SessionMiddleware',
                'django.middleware.common.CommonMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
                'django.contrib.messages.middleware.MessageMiddleware',
            ],
            ROOT_URLCONF='core.urls',
            SECRET_KEY='test-secret-key-for-testing',
            USE_TZ=True,
            DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
            REST_FRAMEWORK={
                'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
                'PAGE_SIZE': 50,
            },
            TEMPLATES=[{
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [os.path.join(base_dir, 'templates')],
                'APP_DIRS': True,
                'OPTIONS': {
                    'context_processors': [
                        'django.template.context_processors.debug',
                        'django.template.context_processors.request',
                        'django.contrib.auth.context_processors.auth',
                        'django.contrib.messages.context_processors.messages',
                    ],
                },
            }],
            STATIC_URL='/static/',
            STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
            ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
        )
        django.setup()

# Fixtures
@pytest.fixture
def mock_station():
    """Create a mock station object."""
    from unittest.mock import Mock
    station = Mock()
    station.id = 1
    station.name = 'Test Station'
    station.retail_price = 3.50
    station.latitude = 41.8781
    station.longitude = -87.6298
    return station

@pytest.fixture
def sample_candidates():
    """Create sample candidate stations for optimizer tests."""
    from unittest.mock import Mock
    stations = []
    for i, (name, price, dist) in enumerate([
        ('Start', 3.50, 0.0),
        ('Cheap', 2.50, 100.0),
        ('Mid', 3.20, 200.0),
        ('Cheaper', 2.30, 300.0),
        ('End', 3.00, 400.0),
    ]):
        s = Mock()
        s.id = i + 1
        s.name = name
        s.retail_price = price
        s.latitude = 40.0
        s.longitude = -90.0 + (dist / 53.0)  # Approximate
        stations.append(s)

    return [
        {'station': s, 'route_distance': d, 'offset_miles': 0.1, 'price': float(s.retail_price)}
        for s, (_, _, d) in zip(stations, [
            ('Start', 3.50, 0.0),
            ('Cheap', 2.50, 100.0),
            ('Mid', 3.20, 200.0),
            ('Cheaper', 2.30, 300.0),
            ('End', 3.00, 400.0),
        ])
    ]