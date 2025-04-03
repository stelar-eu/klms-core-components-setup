FROM quay.io/projectquay/quay:3.11.0

COPY --chown=0:0 /endpoints/api/team.py /quay-registry/endpoints/api/team.py
COPY --chown=0:0 /endpoints/api/appspecifictokens.py /quay-registry/endpoints/api/appspecifictokens.py

ENTRYPOINT ["dumb-init", "--", "/quay-registry/quay-entrypoint.sh"]
CMD ["registry"]