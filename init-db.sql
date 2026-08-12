-- FuelRoute Pro - Database Initialization Script
-- Runs automatically when PostgreSQL container starts for the first time

-- Enable UUID extension for generating UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create application user if it doesn't exist (optional, for additional security)
-- CREATE USER fuelroute_app WITH PASSWORD '${DB_APP_PASSWORD}';
-- GRANT CONNECT ON DATABASE fuelroute TO fuelroute_app;
-- GRANT USAGE ON SCHEMA public TO fuelroute_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fuelroute_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO fuelroute_app;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'FuelRoute Pro database initialized successfully';
    RAISE NOTICE 'Extensions: uuid-ossp enabled';
END $$;