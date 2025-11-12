PYTHON ?= python
UVICORN ?= uvicorn
DOCKER ?= docker
PYTHONPATH ?= src

.PHONY: install run fmt lint test coverage docker-build smoke sbom

install: requirements.txt
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

run:
	PYTHONPATH=$(PYTHONPATH) $(UVICORN) api.main:app --reload --host 0.0.0.0 --port 8000

fmt:
	ruff format

lint:
	ruff check .

test:
	PYTHONPATH=$(PYTHONPATH) pytest --maxfail=1 --disable-warnings --cov=api --cov=agents --cov=tooling

test-acceptance:
	PYTHONPATH=$(PYTHONPATH) pytest tests/test_dropin_agents_acceptance.py

coverage:
	PYTHONPATH=$(PYTHONPATH) pytest --cov --cov-report=term-missing

docker-build:
	$(DOCKER) build -t agent-gateway:latest .

smoke:
	PYTHONPATH=$(PYTHONPATH) pytest tests/test_smoke_gateway.py -s

sbom:
	./scripts/generate_sbom.sh sbom.json
