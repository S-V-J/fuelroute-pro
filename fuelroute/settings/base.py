"""
Django settings for fuelroute project - Base configuration shared across all environments.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-Party Apps
    'rest_framework',
    'drf_spectacular',

    # Local Apps
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fuelroute.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fuelroute.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '300/minute',
        'plan': '30/minute',
    },
}

# DRF Spectacular (OpenAPI) Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'FuelRoute Pro API',
    'DESCRIPTION': 'Plan the cheapest fuel stops on any U.S. route.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Authentication Settings
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'

# External API Configuration (shared)
ROUTING_PROVIDER = os.getenv('ROUTING_PROVIDER', 'osrm_public')
OSRM_PUBLIC_URL = os.getenv('OSRM_PUBLIC_URL', 'https://router.project-osrm.org')
OSRM_SELF_HOSTED_URL = os.getenv('OSRM_SELF_HOSTED_URL', '')
OPENROUTESERVICE_API_KEY = os.getenv('OPENROUTESERVICE_API_KEY', '')
GRAPHHOPPER_API_KEY = os.getenv('GRAPHHOPPER_API_KEY', '')

GEOCODE_PROVIDER = os.getenv('GEOCODE_PROVIDER', 'photon_census')
PHOTON_GEOCODE_URL = os.getenv('PHOTON_GEOCODE_URL', 'https://photon.komoot.io/api/')
CENSUS_GEOCODE_URL = os.getenv('CENSUS_GEOCODE_URL', 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress')

# Defaults
DEFAULT_RANGE_MILES = int(os.getenv('DEFAULT_RANGE_MILES', '500'))
DEFAULT_MPG = float(os.getenv('DEFAULT_MPG', '10'))
DEFAULT_START_FUEL_GALLONS = float(os.getenv('DEFAULT_START_FUEL_GALLONS', '0'))
STATION_BUFFER_MILES = float(os.getenv('STATION_BUFFER_MILES', '25'))
MAX_STATIONS_PER_ROUTE = int(os.getenv('MAX_STATIONS_PER_ROUTE', '5000'))

# Timeouts
HTTP_TIMEOUT_SECONDS = int(os.getenv('HTTP_TIMEOUT_SECONDS', '10'))
CACHE_TIMEOUT_SECONDS = int(os.getenv('CACHE_TIMEOUT_SECONDS', '86400'))