#
# The ontop custom STELAR image
#

#
# Helper stage
#
FROM ontop/ontop:5.0.0 as  ontop-workspace
ARG JDBC_DRIVER=postgresql-42.7.3.jar

#
# Final stage
#
USER 0
WORKDIR /
RUN apt -y update
RUN apt -y install git
RUN git clone https://github.com/stelar-eu/klms-ontology
RUN git clone https://github.com/stelar-eu/klms-core-components-setup
RUN  wget https://jdbc.postgresql.org/download/postgresql-42.7.3.jar


FROM ontop/ontop:5.0.0

USER 0

RUN  mkdir -p /opt/ontop/jdbc
COPY --from=ontop-workspace /postgresql-42.7.3.jar /opt/ontop/jdbc
ENV ONTOP_DB_DRIVER=org.postgresql.Driver

RUN  mkdir -p /opt/ontop/input
COPY --from=ontop-workspace  /klms-ontology/mappings/klms-mappings.obda /opt/ontop/input
ENV ONTOP_MAPPING_FILE=/opt/ontop/input/klms-mappings.obda

COPY --from=ontop-workspace /klms-core-components-setup/knowledge-graph/input/klms-sparql-portal.toml /opt/ontop/input
ENV ONTOP_PORTAL_FILE=/opt/ontop/input/klms-sparql-portal.toml

# Install PostgreSQL client for running the db init scripts
RUN apt-get update && \
    apt-get install -y postgresql-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY start.sh /opt/ontop/startup.sh

# Make the script executable
RUN chmod +x /opt/ontop/startup.sh

COPY ./schemas /opt/ontop/stelar_schemas

ENTRYPOINT ["/opt/ontop/startup.sh"]
CMD ["start-ontop"]

#COPY --from=ontop-workspace /klms-ontology/serializations/klms-ontology.ttl /opt/ontop/input
#ENV ONTOP_ONTOLOGY_FILE=/opt/ontop/input/klms-ontology.ttl
#COPY --from=ontop-workspace /klms-ontology/klms-model.owl /opt/ontop/input
#ENV ONTOP_ONTOLOGY_FILE=/opt/ontop/input/klms-model.owl

