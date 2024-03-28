
DOCKER=docker
IMGTAG=vsam/stelar-okeanos:ckan

.PHONY: all build push


all: build push

build:
	$(DOCKER) build . -t $(IMGTAG)

push:
	$(DOCKER) push $(IMGTAG)

