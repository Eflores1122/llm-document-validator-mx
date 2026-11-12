PYTHON ?= python3

.PHONY: install test lint format generate eval run serve docker

install:
	$(PYTHON) -m pip install -e ".[dev,api]"

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

test: lint
	$(PYTHON) -m pytest

generate:
	$(PYTHON) -m docval generate --out data/golden --cases 24 --seed 42 --force

eval:
	env -u OPENAI_API_KEY -u LLAMA_CLOUD_API_KEY \
		$(PYTHON) -m docval eval --golden data/golden --out reports/eval

run:
	$(PYTHON) -m docval run data/golden --out reports/cases

serve:
	$(PYTHON) -m uvicorn docval.api:app --host 127.0.0.1 --port 8000

docker:
	docker build -t docval:local .
