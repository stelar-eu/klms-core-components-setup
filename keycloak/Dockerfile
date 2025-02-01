FROM quay.io/keycloak/keycloak:25.0

WORKDIR /opt/keycloak

COPY /theme /opt/keycloak/providers/

RUN /opt/keycloak/bin/kc.sh build

ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--features=token-exchange,admin-fine-grained-authz"]
