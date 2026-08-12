"""
Django settings for fuelroute project - Testing environment.
Fast settings for CI/CD pipeline.
"""
from .base import *

# Disable debug for testing
DEBUG = False

# Use a fixed secret key for testing
SECRET_KEY = 'django-insecure-test-key-for-testing-only'

# Allow test hosts
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

# Database - In-memory SQLite for speed
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Email - Locmem backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Cache - Locmem for testing
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}

# Password hashers - Use fast hasher for testing
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Static files - Simple storage for testing
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Disable CSP in testing
CSP_REPORT_ONLY = True

# Reduce logging noise in tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}