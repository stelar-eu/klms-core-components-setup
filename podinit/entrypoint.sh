#!/bin/sh

# Check the first argument
if [ "$1" = "postgresql" ]; then
  shift
  # Construct the DB_URL if the service type is postgresql
  DB_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}/${POSTGRES_DB}?sslmode=disable"
  exec wait4x postgresql "$DB_URL" "$@"
else
  # For other types like "http" or "redis", just pass the arguments directly
  exec wait4x "$@"
fi