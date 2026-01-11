#!/bin/bash
set -e

echo "Se crea baza de date keycloak"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE keycloak;
EOSQL

echo "Keycloak BD creata cu succes!"