#!/bin/bash
set -e

echo "Creating keycloak database..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE keycloak;
EOSQL

echo "Keycloak database created successfully!"