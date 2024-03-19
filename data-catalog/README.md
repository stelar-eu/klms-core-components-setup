# Docker Compose setup for Data Catalog in CKAN


* [Overview](#overview)
* [Installing Docker](#installing-docker)
* [docker compose vs docker-compose](#docker-compose-vs-docker-compose)
* [Install CKAN plus dependencies](#install-ckan-plus-dependencies)


## 1.  Overview

This is a set of configuration and setup files to run the KLMS Data Catalog as a CKAN site.

The CKAN images used are from the official CKAN [ckan-docker](https://github.com/ckan/ckan-docker-base) repo

The non-CKAN images are as follows:

* DataPusher: CKAN's [pre-configured DataPusher image](https://github.com/ckan/ckan-base/tree/main/datapusher).
* PostgreSQL: Official PostgreSQL image. Database files are stored in a named volume.
* Solr: CKAN's [pre-configured Solr image](https://github.com/ckan/ckan-solr). Index data is stored in a named volume.
* Redis: standard Redis image
* NGINX: latest stable nginx image that includes SSL and Non-SSL endpoints

The site is configured using environment variables that you can set in the `.env` file.

## 2.  Installing Docker

Install Docker by following the following instructions: [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)

To verify a successful Docker installation, run `docker run hello-world` and `docker version`. These commands should output 
versions for client and server.

## 3.  docker compose *vs* docker-compose

All Docker Compose commands in this README will use the V2 version of Compose ie: `docker compose`. The older version (V1) 
used the `docker-compose` command. Please see [Docker Compose](https://docs.docker.com/compose/compose-v2/) for
more information.

## 4.  Prepare CKAN plus dependencies for KLMS (Base mode)

Use this if you are a maintainer and will not be making code changes to CKAN or to CKAN extensions.

Copy the included `.env.example` and rename it to `.env`. Modify it depending on your own needs.

*IMPORTANT!* To install [PostGIS extension](https://postgis.net/) and make it accessible from the PostgreSQL database used by CKAN, in the `Dockerfile` under directory `ckan-docker/postgresql/` specify this image:

`FROM postgis/postgis:12-3.3-alpine`

instead of `FROM postgres:12-alpine`.

*IMPORTANT!* The docker compose file also specifies SQL scripts located under directory `/schema-extension` that will be executed in the PostgreSQL database in order to create custom schemata for KLMS ontology, as well as metadata about workflows (AirFlow) and tasks (MLFlow).

Specify extra volumes (e.g., for optional SQL scripts) and port mappings in the respective sections in `docker-compose.yml`:

	volumes:
	  ...
	  pg_scripts:
	  ...
	services:
	  ...
	
	 db:
		...
	  	context: postgresql
	  	...
	  	- ./pg_scripts/30_custom_schemata.sql:/docker-entrypoint-initdb.d/30_custom_schemata.sql


This SQL script will be used to create custom schemata (KLMS ontology, workflow metadata) in the same database used and maintained by CKAN.

*IMPORTANT!* Make sure that this `30_custom_schemata.sql` file is copied under `pg_scripts` and it has enabled execution permissions for all users. 


## 5.  Install (build and run) CKAN plus dependencies (Base mode)

When accessing CKAN directly (via a browser) ie: not going through NGINX you will need to make sure you have "ckan" set up
to be an alias to localhost in the local hosts file. Either that or you will need to change the `.env` entry for CKAN_SITE_URL

Using the default values on the `.env.example` file will get you a working CKAN instance. There is a sysadmin user created by default with the values defined in `CKAN_SYSADMIN_NAME` and `CKAN_SYSADMIN_PASSWORD`(`ckan_admin` and `test1234` by default). This should be obviously changed before running this setup as a public CKAN instance.

To build the images:

	docker compose build

To start the containers:

	docker compose up

This will start up the containers in the current window. By default the containers will log direct to this window with each container
using a different colour. You could also use the -d "detach mode" option ie: `docker compose up -d` if you wished to use the current 
window for something else.

At the end of the container start sequence there should be 6 containers running

![Screenshot 2022-12-12 at 10 36 21 am](https://user-images.githubusercontent.com/54408245/207012236-f9571baa-4d99-4ffe-bd93-30b11c4829e0.png)

After this step, CKAN should be running at `CKAN_SITE_URL`.

*CAUTION!* If CKAN plugins (e.g., [geospatial](https://github.com/ckan/ckanext-spatial), [keycloak](https://github.com/keitaroinc/ckanext-keycloak)) have been specified in the `.env` file, then the status of CKAN deployment will be shown as waiting. Stop deployment (Ctrl+C) after a few minutes once all images have been created. Containers for `ckan` and `nginx` should be manually restarted after the specified plugins have been installed from within the container.

## 6.  Post-install configuration for CKAN

Once `ckan` container is up-and-running, enter inside the container:

	docker exec -u root -it ckan /bin/bash -c "export TERM=xterm; exec bash"

Configuration file in the ckan container can be found in this path: `/srv/app/ckan.ini`. Open the config and modify this property to set it to the publicly accessible URL:

	ckan.site_url = CKAN_SITE_URL

Also, specify the correct credentials (user, password, database) for connection to PostgreSQL database:

	sqlalchemy.url = postgresql://<ckan-user>:<ckan-pass>@db/<ckan-database>

Then, exit the container and restart it:

	docker restart ckan

At this stage, a healthy CKAN installation should be available with its GUI at the publicly accessible URL (unless plugins have NOT been installed yet). Use the admin credentials to enter the GUI and create organizations and users, publish packages, etc.
