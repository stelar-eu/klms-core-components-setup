
DOCKER=docker
IMGTAG=petroud/stelar-tuc:dbinit

.PHONY: all build push


all: build push

build:
	$(DOCKER) build . -t $(IMGTAG)

push:
	$(DOCKER) push $(IMGTAG)

