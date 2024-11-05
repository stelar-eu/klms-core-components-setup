
DOCKER=docker
IMGTAG=petroud/stelar-tuc:kcinit

.PHONY: all build push


all: build push

build:
	$(DOCKER) build . -t $(IMGTAG)

push:
	$(DOCKER) push $(IMGTAG)

