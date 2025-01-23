#!/bin/bash
set -e

#Create 'stelar' database and ckan user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE ROLE "$CKAN_DB_USER" NOSUPERUSER CREATEDB CREATEROLE LOGIN PASSWORD '$CKAN_DB_PASSWORD';
    CREATE DATABASE "$CKAN_DB" OWNER "$CKAN_DB_USER" ENCODING 'utf-8';
EOSQL

# Connect to the newly created database and enable the PostGIS extension
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" "$CKAN_DB" <<-EOSQL
    CREATE EXTENSION postgis;
EOSQL

# Create the datastore user and db 
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE ROLE "$DATASTORE_READONLY_USER" NOSUPERUSER NOCREATEDB NOCREATEROLE LOGIN PASSWORD '$DATASTORE_READONLY_PASSWORD';
    CREATE DATABASE "$DATASTORE_DB" OWNER "$CKAN_DB_USER" ENCODING 'utf-8';
EOSQL

# Connect to the newly created database and enable the PostGIS extension
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" "$DATASTORE_DB" <<-EOSQL
    CREATE EXTENSION postgis;
EOSQL

# Create Keycloak user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE ROLE "$KEYCLOAK_DB_USER" NOSUPERUSER CREATEDB CREATEROLE LOGIN PASSWORD '$KEYCLOAK_DB_PASSWORD';
EOSQL

# Connect to the newly created database and create the schema
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" "$KEYCLOAK_DB" <<-EOSQL
    CREATE SCHEMA "$KEYCLOAK_DB_SCHEMA";
EOSQL

# Assign privileges on the keycloak schema to the Keycloak user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" "$KEYCLOAK_DB" <<-EOSQL
    GRANT ALL PRIVILEGES ON SCHEMA "$KEYCLOAK_DB_SCHEMA" TO "$KEYCLOAK_DB_USER";
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA "$KEYCLOAK_DB_SCHEMA" TO "$KEYCLOAK_DB_USER";
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA "$KEYCLOAK_DB_SCHEMA" TO "$KEYCLOAK_DB_USER";
EOSQL
