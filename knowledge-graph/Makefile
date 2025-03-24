
DOCKER=docker
IMGTAG=petroud/stelar-tuc:ontop

.PHONY: all build push


all: build push

build:
	$(DOCKER) build . --no-cache -t $(IMGTAG)

push:
	$(DOCKER) push $(IMGTAG)

