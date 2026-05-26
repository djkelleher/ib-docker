.PHONY: test pre-commit lint compose-check build-gateway build-tws

test:
	pytest

pre-commit:
	pre-commit run --all-files

lint: pre-commit

compose-check:
	docker compose config -q

build-gateway:
	docker build -t ib-gateway-dev --build-arg PROGRAM=ibgateway build/

build-tws:
	docker build -t ib-tws-dev --build-arg PROGRAM=tws build/
