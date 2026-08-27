VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.DEFAULT_GOAL := help
.PHONY: help setup build-web demo run serve test lint typecheck fmt check clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create the venv, install the package + dev tools, build the dashboard
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"
	$(MAKE) build-web
	@echo "\nReady.  cp .env.example .env  (optional)  then:  make demo"

build-web: ## Build the React dashboard into the Python package
	cd frontend && npm install --silent && npm run build

run: ## Run the pipeline once, write data/pipeline_report.json
	$(PY) -m revenue_recovery.cli run

demo: ## Run the pipeline, then serve the dashboard at :8000
	$(PY) -m revenue_recovery.cli demo

serve: ## Serve the API + dashboard (assumes a report exists)
	$(PY) -m revenue_recovery.cli serve --reload

test: ## Run the test suite with coverage
	$(PY) -m pytest

lint: ## ruff check
	$(VENV)/bin/ruff check src tests

typecheck: ## mypy (strict)
	$(VENV)/bin/mypy src

fmt: ## ruff format + autofix
	$(VENV)/bin/ruff format src tests
	$(VENV)/bin/ruff check --fix src tests

check: lint typecheck test ## Everything CI runs

clean: ## Remove caches and generated artefacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build
	rm -f data/*.json
	find . -name __pycache__ -type d -not -path './.venv/*' -not -path './frontend/*' -exec rm -rf {} + 2>/dev/null || true
