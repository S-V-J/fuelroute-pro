"""
Django settings for fuelroute project - Production environment.
"""
import os
import dj_database_url
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# SECURITY WARNING: keep the secret key used in production secret!
# No fallback - must be set in environment
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Explicit allowlist from environment
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# Security headers (overridable via env for testing)
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "True") == "True"
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "True") == "True"
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Content Security Policy
INSTALLED_APPS += ['csp']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'csp.middleware.CSPMiddleware',  # CSP after WhiteNoise
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CONTENT_SECURITY_POLICY = {
    "default-src": "'self'",
    "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
    "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
    "img-src": "'self' data: https://*.tile.openstreetmap.org https://cdn.jsdelivr.net",
    "font-src": "'self' https://cdn.jsdelivr.net",
    "connect-src": "'self' https://router.project-osrm.org https://photon.komoot.io https://geocoding.geo.census.gov",
    "frame-ancestors": "'none'",
}

# Database - PostgreSQL with connection pooling (or SQLite for local testing)
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres"):
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=60,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
else:
    # SQLite fallback for local testing of production settings
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Cache - Redis (with local memory fallback for testing)
REDIS_URL = os.environ.get("CACHES_REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
                "IGNORE_EXCEPTIONS": True,
            },
            "KEY_PREFIX": "fuelroute",
            "TIMEOUT": 300,
        },
        "sessions": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "KEY_PREFIX": "session",
        },
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "sessions"
else:
    # Local memory fallback for testing production settings without Redis
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'production-test-cache',
        }
    }

# Email - Production backend (SendGrid)
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
if SENDGRID_API_KEY:
    EMAIL_BACKEND = "sendgrid_backend.SendgridBackend"
    DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@fuelroute.pro")
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
else:
    # Fallback to console for local testing
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    import logging
    logging.getLogger(__name__).warning("SENDGRID_API_KEY not set - using console email backend")

# WhiteNoise with ManifestStaticFilesStorage for production
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
WHITENOISE_MAX_AGE = 31536000  # 1 year for fingerprinted files
WHITENOISE_USE_FINDERS = True
WHITENOISE_MANIFEST_STRICT = False

# Prometheus metrics
INSTALLED_APPS = ['django_prometheus'] + INSTALLED_APPS
MIDDLEWARE = ['django_prometheus.middleware.PrometheusBeforeMiddleware'] + MIDDLEWARE + ['django_prometheus.middleware.PrometheusAfterMiddleware']

# Sentry integration (optional - requires SENTRY_DSN env var)
if os.environ.get("SENTRY_DSN"):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR
    )

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        integrations=[DjangoIntegration(), RedisIntegration(), sentry_logging],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        release=os.environ.get("APP_VERSION", "unknown"),
        send_default_pii=False,
    )

# Structured JSON logging
import uuid

class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = getattr(record, "correlation_id", str(uuid.uuid4())[:8])
        return True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s",
        },
    },
    "filters": {
        "correlation_id": {"()": CorrelationIdFilter},
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["correlation_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "core": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "httpx": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}