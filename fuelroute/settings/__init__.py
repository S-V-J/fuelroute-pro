# FuelRoute Pro Settings Package
# Import the appropriate settings module based on DJANGO_SETTINGS_MODULE env var

# This file exists to make fuelroute.settings a package
# The actual settings are loaded via DJANGO_SETTINGS_MODULE environment variable
# which should be set to one of:
#   - fuelroute.settings.development
#   - fuelroute.settings.production
#   - fuelroute.settings.testing