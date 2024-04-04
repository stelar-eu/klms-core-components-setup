
DOCKER=docker
IMGTAG=vsam/stelar-okeanos:postgis

.PHONY: all build push


all: build push

build:
	$(DOCKER) build . -t $(IMGTAG)

push:
	$(DOCKER) push $(IMGTAG)

