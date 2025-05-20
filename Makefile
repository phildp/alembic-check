.PHONY: venv test lint clean

help: ## Display this help.
	@echo "Please use 'make <target>' where <target> is one of the following:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

venv: ## Create a virtual environment and install dependencies
	python -m pip install --upgrade pip
	pip install uv==0.7.6
	uv venv
	uv pip install -e ".[dev]"

test: venv ## Run tests
	uv run pytest ${args} --cov=alembic_check --cov-report=xml 

pre-commit: venv ## Run pre-commit
	uv run pre-commit run ${args}

clean: ## Clean up
	rm -rf .venv
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .coverage
	rm -rf htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete 