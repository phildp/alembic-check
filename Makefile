VENV = .venv
UV = uv
PYTHON = $(VENV)/bin/python
PIP = pip3

.PHONY: help init venv test pre-commit clean

help: ## Display this help.
	@echo "Please use 'make <target>' where <target> is one of the following:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

init: ## Initialize the virtual environment
	$(PIP) install --upgrade pip
	$(PIP) install uv==0.7.6
	$(UV) sync --all-groups
	$(UV) pip install -e .
	@touch $(VENV)/bin/activate

test: init ## Run tests
	$(UV) run pytest ${args} --cov=alembic_check --cov-report=xml 

pre-commit: init ## Run pre-commit
	$(UV) run pre-commit run ${args}

clean: ## Clean up
	rm -rf .venv
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .coverage
	rm -rf htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete 