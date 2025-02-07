
##### THE CKAN DOCKERFILE IN PLAIN SIGHT HERE #####
FROM alpine:3.17
ARG CKAN_VERSION=ckan-2.10.5

# Internals, you probably don't need to change these
ENV TZ=UTC
ENV APP_DIR=/srv/app
ENV SRC_DIR=/srv/app/src
ENV CKAN_INI=${APP_DIR}/ckan.ini
ENV PIP_SRC=${SRC_DIR}
ENV CKAN_STORAGE_PATH=/var/lib/ckan
ENV GIT_URL=https://github.com/ckan/ckan.git
# CKAN version to build
ENV GIT_BRANCH=${CKAN_VERSION}
# Customize these on the .env file if needed
ENV CKAN_SITE_URL=http://localhost:5000
ENV CKAN__PLUGINS="image_view text_view recline_view datastore envvars"

# UWSGI options
ENV UWSGI_HARAKIRI=50

WORKDIR ${APP_DIR}

# Set up timezone
RUN apk add --no-cache tzdata
RUN echo ${TZ} > /etc/timezone
# Make sure both files are not exactly the same
RUN if ! [ /usr/share/zoneinfo/${TZ} -ef /etc/localtime ]; then \
        cp /usr/share/zoneinfo/${TZ} /etc/localtime ;\
    fi ;

# Install necessary packages to run CKAN
RUN apk add --no-cache git \
        gettext \
        postgresql-client \
        python3 \
        libxml2 \
        libxslt \
        musl-dev \
        uwsgi \
        uwsgi-http \
        uwsgi-corerouter \
        uwsgi-python \
        libmagic \
        curl \
        patch \
        bash && \
    # Packages to build CKAN requirements and plugins
    apk add --no-cache --virtual .build-deps \
        postgresql-dev \
        gcc \
        make \
        g++ \
        autoconf \
        automake \
    	libtool \
        python3-dev \
        libxml2-dev \
        libxslt-dev \
        linux-headers \
        openssl-dev \
        libffi-dev \
        cargo && \
    # Create SRC_DIR
    mkdir -p ${SRC_DIR} && \
    # Install pip, supervisord and uwsgi
    curl -o ${SRC_DIR}/get-pip.py https://bootstrap.pypa.io/get-pip.py && \
    python3 ${SRC_DIR}/get-pip.py && \
    pip3 install supervisor && \
    mkdir /etc/supervisord.d && \
    rm -rf ${SRC_DIR}/get-pip.py

COPY setup/supervisord.conf /etc

# Install CKAN
RUN pip3 install -e git+${GIT_URL}@${GIT_BRANCH}#egg=ckan && \
    cd ${SRC_DIR}/ckan && \
    pip3 install --no-binary markdown -r requirements.txt && \
    # Install CKAN envvars to support loading config from environment variables
    pip3 install -e git+https://github.com/okfn/ckanext-envvars.git@v0.0.6#egg=ckanext-envvars
    # Create and update CKAN config
    # ckan generate config ${CKAN_INI} && \
    # ckan config-tool ${CKAN_INI} "beaker.session.secret = " && \
    # ckan config-tool ${CKAN_INI} "ckan.plugins = ${CKAN__PLUGINS}"

# Create a local user and group to run the app
RUN addgroup -g 92 -S ckan && \
    adduser -u 92 -h /home/ckan -s /bin/bash -D -G ckan ckan

# Create local storage folder
RUN mkdir -p ${CKAN_STORAGE_PATH} && \
    chown -R ckan:ckan ${CKAN_STORAGE_PATH}

ADD https://raw.githubusercontent.com/ckan/ckan/${GIT_BRANCH}/wsgi.py ${APP_DIR}
RUN chmod 644 ${APP_DIR}/wsgi.py

# Create entrypoint directory for children image scripts
ONBUILD RUN mkdir /docker-entrypoint.d



############################## SETUP EXTENSIONS SRC ###############################
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

#################################################################################

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

# Copy requirements and install python libs using pip 
COPY ./requirements.txt /srv/app
RUN pip install --no-cache-dir -r requirements.txt

# Copy custom initialization scripts
COPY docker-entrypoint.d/* /docker-entrypoint.d/

# Use the custom start_ckan.sh script
COPY setup/start_ckan.sh /srv/app/start_ckan.sh

# Use the custom prerun.py script
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

EXPOSE 5000

### DERIVED FROM CKAN ORIGINAL DOCKERFILE
ENTRYPOINT ["/srv/app/start_ckan.sh"]