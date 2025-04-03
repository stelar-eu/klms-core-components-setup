#!/bin/sh

# Check the first argument passed to the container
if [ "$1" = "setup" ]; then
    echo "[CKAN_SETUP] Running setup CKAN phase..."
    echo " "

    echo "[CKAN_SETUP] Generating ckan.ini file in ${CKAN_INI}..."
    ckan generate config ${CKAN_INI} && \
    ckan config-tool ${CKAN_INI} "beaker.session.secret = " && \
    ckan config-tool ${CKAN_INI} "ckan.plugins = ${CKAN__PLUGINS}" 

    if grep -E "beaker.session.secret ?= ?$" ckan.ini; then
        echo "[CKAN_SETUP] Setting beaker.session.secret in ini file"
        ckan config-tool $CKAN_INI "beaker.session.secret=${CKAN___BEAKER__SESSION__SECRET}"
        ckan config-tool $CKAN_INI "WTF_CSRF_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe())')"
        ckan config-tool $CKAN_INI "api_token.jwt.encode.secret=${CKAN___API_TOKEN__JWT__ENCODE__SECRET}"
        ckan config-tool $CKAN_INI "api_token.jwt.decode.secret=${CKAN___API_TOKEN__JWT__DECODE__SECRET}"
    fi
    echo " "

    # Additional CKAN setup tasks
    echo "[CKAN_SETUP] Setting up CKAN configuration..."
    ckan config-tool $CKAN_INI ckan.datapusher.api_token=xxx
    echo " "

    # Run prerun.py script to init database, admin user etc.
    echo "[CKAN_SETUP] Running prerun script to initialize CKAN extensions and create the default admin user..."
    python3 prerun.py
    echo " "

    # Pass the normal datapusher api_token to ckan.ini
    echo "[CKAN_SETUP] Setting up ckan.datapusher.api_token in the CKAN config file..."
    ckan config-tool $CKAN_INI "ckan.datapusher.api_token=$(ckan -c $CKAN_INI user token add ckan_admin datapusher | tail -n 1 | tr -d '\t')"
    echo " "

    # Run any startup scripts provided by images extending this one
    if [[ -d "/docker-entrypoint.d" ]]; then
        for f in /docker-entrypoint.d/*; do
            case "$f" in
                *.sh)     echo "[ENTRYPOINT] $0: Running init file $f"; . "$f" ;;
                *.py)     echo "[ENTRYPOINT] $0: Running init file $f"; python3 "$f"; echo ;;
                *)        echo "[ENTRYPOINT] $0: Ignoring $f (not an sh or py file)" ;;
            esac
            echo
        done
    fi

elif [ "$1" = "start-server" ]; then
    echo "[CKAN_RUN] Starting CKAN server with extension installation and UWSGI..."

    cp /srv/stelar/config/ckan.ini /srv/app/ckan.ini

    # Set the common UWSGI options
    UWSGI_OPTS="--plugins http,python \
                --socket /tmp/uwsgi.sock \
                --wsgi-file /srv/app/wsgi.py \
                --http 0.0.0.0:5000 \
                --master --enable-threads \
                --lazy-apps \
                -p 2 -L -b 32768 --vacuum \
                --harakiri $UWSGI_HARAKIRI"

    echo "[CKAN_RUN] Starting supervisord..."
    # Start supervisord
    supervisord --configuration /srv/app/etc/supervisord.conf &

    echo "[CKAN_RUN] Starting UWSGI with the configured options..."
    # Start uwsgi
    uwsgi $UWSGI_OPTS

else
    echo "[ERROR] Invalid argument. Use 'setup' to initialize or 'start-server' to run the server."
    exit 1
fi