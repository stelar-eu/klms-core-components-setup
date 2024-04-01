# Docker Compose setup for the STELAR Knowledge Graph in Ontop

## 1.  Overview

This is a set of configuration and setup files to expose the STELAR Knowledge Graph as a virtual RDF graph via [Ontop](https://ontop-vkg.org/).

The Ontop image `ontop/ontop` used is from the official repository [ontop-docker](https://github.com/ontop/ontop/tree/version5/client/docker).


## 2.  Bootstrapping of Ontop v5.0.0 against an existing PostgreSQL database 

Make sure you have write/execution privileges in a `PWD` working directory (e.g., `/home/user/ontop`) in your local machine. 

Connection details to an existing PostgreSQL database must be specified as in [`db.properties'](./input/db.properties) file and stored in subfolder `PWD/input/`.

Download a [JDBC driver for PostgreSQL](https://jdbc.postgresql.org/download/) and place the JAR file in subfolder `PWD/jdbc/`.

Bootstrapping allows the automatic generation of mappings (`klms-mappings.obda`) and ontology (`klms-ontology.ttl`) starting from the database schema. Bootstrap mappings will be created automatically by directly mapping all tables in the database. The generated output can be used as-is or further edited and customized manually (e.g., to used different ontological modeling choices and corresponding mappings). 

	docker run -it \ 
		--add-host=host.docker.internal:host-gateway \ 
		-v $PWD/input:/opt/ontop/input \ 
		-v $PWD/jdbc:/opt/ontop/jdbc \ 
		-e ONTOP_PROPERTIES_FILE=/opt/ontop/input/db.properties \ 
		-e ONTOP_ONTOLOGY_FILE=/opt/ontop/input/klms-ontology.ttl \ 
		-e ONTOP_MAPPING_FILE=/opt/ontop/input/klms-mappings.obda \ 
		--name ontop \ 
		ontop/ontop \ 
		ontop bootstrap \ 
		-b http://klms.stelar-project.eu/ 

 
*IMPORTANT!* Finally, remove the created container, as it was used solely for bootstrapping:

	docker rm ontop 

 
## 3.  Deployment of STELAR Knowledge Graph via Ontop 5.0.0

*IMPORTANT!* The auto-generated mappings from the previous step need editing to reflect information from the STELAR Data Catalog that will be exposed in the RDF graph. *Replace* file `klms-mappings.obda` with the [KLMS mappings](https://github.com/stelar-eu/klms-ontology/blob/main/mappings/klms-mappings.obda) to the KLMS Ontology to include metadata from the STELAR Data Catalog (in CKAN), KLMS ontology, and the STELAR Tracking Server (held in separate schemata in PostgreSQL). 

Also, *replace* the auto-generated `klms-ontology.ttl` with the actual KLMS ontology either in [OWL](https://github.com/stelar-eu/klms-ontology/blob/main/klms-model.owl) or in [Turtle serialization](https://github.com/stelar-eu/klms-ontology/blob/main/serializations/klms-ontology.ttl).

Start the container for the SPARQL endpoint at the default port (8080) or another <PORT> (e.g., 9056 by mapping to 8080) using the prepared mappings: 

	docker run -d --name ontop \
		--add-host=host.docker.internal:host-gateway \
		-v $PWD/input:/opt/ontop/input \
		-v $PWD/jdbc:/opt/ontop/jdbc \
		-e ONTOP_PROPERTIES_FILE=/opt/ontop/input/db.properties \
		-e ONTOP_ONTOLOGY_FILE=/opt/ontop/input/klms-ontology.ttl \
		-e ONTOP_MAPPING_FILE=/opt/ontop/input/klms-mappings.obda \
		-p <PORT>:8080 ontop/ontop 

 
Note that any subsequent changes of mappings in file `klms-mappings.obda` require restarting the container: 

	docker restart ontop 

 
## 4.  Testing SPARQL endpoint

Queries can be submitted to the SPARQL endpoint available at `https://localhost/<PORT>/`. Example:  

	PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
	PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
	SELECT * WHERE { 
	  ?sub ?pred ?obj . 
	} 
	LIMIT 10 
