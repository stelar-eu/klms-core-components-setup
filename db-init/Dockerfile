FROM ckan/ckan-base:2.10.4

WORKDIR /srv/app
# 
# Custom supervisord.conf to avoid user permission problems
# This is needed in order to configure supervisor with the 
# permissions of  ckan:ckan (user:group).
# 
#
RUN mkdir -p /srv/app/etc
RUN mkdir -p /srv/app/etc/supervisord.d
COPY setup/supervisord.conf /srv/app/etc

# Copy requirements and install python libs using pip 
COPY ./requirements.txt /srv/app
RUN pip install --no-cache-dir -r requirements.txt

# Copy custom SQL files in the <app>/etc directory. Used to init schemas for STELAR KLMS, OnTop etc.
COPY schema-extensions/30_custom_schemata.sql /srv/app/etc/custom_schemata.sql
COPY schema-extensions/40_custom_functions.sql /srv/app/etc/custom_functions.sql
COPY schema-extensions/50_custom_views.sql /srv/app/etc/custom_views.sql

# Copy custom initialization scripts
COPY docker-entrypoint.d/* /docker-entrypoint.d/

# Use the custom start_ckan.sh script
COPY setup/start_ckan.sh.stelar-init /srv/app/start_ckan.sh

# Use the custom prerun.py
COPY setup/prerun.py /srv/app/prerun.py

# Apply any patches needed to CKAN core or any of the built extensions (not the
# runtime mounted ones)
COPY patches ${APP_DIR}/patches

RUN for d in $APP_DIR/patches/*; do \
        if [ -d $d ]; then \
            for f in `ls $d/*.patch | sort -g`; do \
                cd $SRC_DIR/`basename "$d"` && echo "$0: Applying patch $f to $SRC_DIR/`basename $d`"; patch -p1 < "$f" ; \
            done ; \
        fi ; \
    done

# Make everything owned by ckan:ckan
RUN chown ckan:ckan -R /srv/app
