FROM postgis/postgis:12-3.3-alpine

# Include extra setup scripts (eg datastore)
COPY --chown=postgres:postgres docker-entrypoint-initdb.d /docker-entrypoint-initdb.d
