# FuelRoute Pro - Makefile
# Common development and deployment commands

.PHONY: help install migrate seed run test lint format clean docker-build docker-up docker-down docker-logs

# Default target
help:
	@echo "FuelRoute Pro - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install      - Install Python dependencies"
	@echo "  make migrate      - Run database migrations"
	@echo "  make seed         - Import fuel station data (requires CSV file)"
	@echo "  make run          - Start development server"
	@echo "  make test         - Run test suite"
	@echo "  make lint         - Run code linting (flake8)"
	@echo "  make format       - Format code (black + isort)"
	@echo "  make clean        - Clean up generated files"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-up    - Start services with docker-compose"
	@echo "  make docker-down  - Stop services"
	@echo "  make docker-logs  - View service logs"
	@echo ""
	@echo "Data Management:"
	@echo "  make import-fuel  - Import fuel prices from CSV"
	@echo "  make geocode      - Geocode stations missing coordinates"

# Python and virtual environment
VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
DJANGO = $(PYTHON) manage.py

# Install dependencies
install: $(VENV)/bin/activate
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

# Database migrations
migrate:
	$(DJANGO) migrate

makemigrations:
	$(DJANGO) makemigrations

# Data import commands
import-fuel:
	@if [ -f "data/fuel-prices-for-be-assessment.csv" ]; then \
		$(DJANGO) import_stations data/fuel-prices-for-be-assessment.csv; \
	else \
		echo "Error: CSV file not found at data/fuel-prices-for-be-assessment.csv"; \
		exit 1; \
	fi

geocode:
	$(DJANGO) geocode_stations

# Seed is an alias for import-fuel + geocode
seed: import-fuel geocode

# Development server
run:
	$(DJANGO) runserver 0.0.0.0:8000

# Testing
test:
	$(PYTHON) -m pytest tests/ -v

test-cov:
	$(PYTHON) -m pytest tests/ --cov=core --cov-report=term-missing

# Code quality
lint:
	$(VENV)/bin/flake8 core/ tests/ --max-line-length=100 --ignore=E501,W503

format:
	$(VENV)/bin/black core/ tests/
	$(VENV)/bin/isort core/ tests/

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf $(VENV)

# Docker commands
docker-build:
	docker build -t fuelroute-pro:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-shell:
	docker-compose exec web bash

# Full setup for new developers
setup: install migrate seed
	@echo ""
	@echo "Setup complete! Run 'make run' to start the server."
	@echo "Then visit http://localhost:8000"

# Production-like setup
prod-setup: docker-build
	docker-compose up -d
	@echo "Waiting for services to start..."
	@sleep 5
	docker-compose exec web python manage.py migrate
	docker-compose exec web python manage.py import_stations data/fuel-prices-for-be-assessment.csv
	docker-compose exec web python manage.py geocode_stations
	@echo ""
	@echo "Production setup complete! Visit http://localhost:8000"