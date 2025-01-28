#!/bin/sh


# Check if the first argument is 'start-ontop'
if [ "$1" = 'start-ontop' ]; then
    exec /opt/ontop/entrypoint.sh
# Check if the first argument is 'setup-db'
elif [ "$1" = 'setup-db' ]; then
    echo "Setting up the database..."

    # Construct the PostgreSQL URL
    psql='/usr/bin/psql'  # psql executable
    URL="postgresql://${ONTOP_DB_USER}:${ONTOP_DB_PASSWORD}@${ONTOP_DB_HOST}/${ONTOP_DB}"  # Constructing the db URI

    # Check if psql is executable
    if ! [ -x "$psql" ]; then
        echo "Error: $psql cannot be executed, skipping SQL execution"
        exit 1
    fi

    # Loop over all .sql files in /schemas and execute them
    for sql_file in /opt/ontop/stelar_schemas/*.sql; do
        if [ -f "$sql_file" ]; then  # Check if the file exists
            echo "Executing $sql_file..."
            psql "$URL" "-v" "ON_ERROR_STOP=on" "-f" "$sql_file"
            
            # Check the exit status
            if [ $? -ne 0 ]; then
                echo "Error executing $sql_file"
                exit 1
            fi
        else
            echo "No SQL files found in /schemas."
        fi
    done
else
    echo "Invalid command. Use 'start-ontop' or 'setup-db'."
    exit 1
fi
