FROM ckan/ckan-base:2.10.4

# Install any extensions needed by your CKAN instance
# See Dockerfile.dev for more details and examples


# EXTENSION: keycloak
# The keycloak connection.  N.B.  Eventually we shall need to clone this
# repository, to avoid future breakage
#

WORKDIR /srv/app/src
RUN git clone https://github.com/keitaroinc/ckanext-keycloak.git
WORKDIR /srv/app/src/ckanext-keycloak
RUN pip install -e .
RUN pip install -r requirements.txt

# EXTENSIONS: geoview
WORKDIR /srv/app/src 
RUN git clone https://github.com/ckan/ckanext-geoview.git
WORKDIR /srv/app/src/ckanext-geoview 
RUN pip install -r dev-requirements.txt 
RUN python setup.py install 
RUN python setup.py develop 


# EXTENSION: spatial
RUN apk add proj-dev
RUN apk add proj-util
RUN apk add geos-dev

ENV PROJ_DIR=/usr
ENV PROJ_INCDIR=/usr/include
ENV PROJ_LIBDIR=/usr/lib
ENV PROJ_WHEEL=1

WORKDIR /srv/app/src
RUN git clone https://github.com/stelar-eu/ckanext-spatial-stelar.git ckanext-spatial  --branch stelar --depth 1

WORKDIR /srv/app/src/ckanext-spatial
RUN pip install -r requirements.txt
RUN pip install -r requirements-postgis.txt
RUN python setup.py install
RUN python setup.py develop



#
# --------- END OF EXTENSIONS -------------------
#

# Restore WORKDIR after extensions are installed
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

# Copy custom schema file in the <app>/etc directory
COPY setup/30_custom_schemata.sql /srv/app/etc/custom_schemata.sql


# Copy custom initialization scripts
COPY docker-entrypoint.d/* /docker-entrypoint.d/

# Use the custom start_ckan.sh script
COPY setup/start_ckan.sh.stelar-okeanos /srv/app/start_ckan.sh

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
