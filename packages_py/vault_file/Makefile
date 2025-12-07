.PHONY: install dev-install test test-cov lint type-check format clean run help

# Default target
help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies with Poetry"
	@echo "  make dev-install  - Install with dev dependencies"
	@echo "  make test         - Run tests with pytest"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo "  make lint         - Run ruff linter"
	@echo "  make type-check   - Run mypy type checker"
	@echo "  make format       - Format code with ruff"
	@echo "  make clean        - Remove cache and build artifacts"
	@echo "  make run          - Run the module (example usage)"
	@echo "  make all          - Run lint, type-check, and tests"

# Install production dependencies
install:
	poetry install --only main

# Install all dependencies including dev
dev-install:
	poetry install

# Run tests
test:
	poetry run pytest

# Run tests with coverage
test-cov:
	poetry run pytest --cov=. --cov-report=term-missing --cov-report=html

# Run linter
lint:
	poetry run ruff check .

# Run type checker
type-check:
	poetry run mypy .

# Format code
format:
	poetry run ruff format .
	poetry run ruff check --fix .

# Clean up cache and build artifacts
clean:
	rm -rf __pycache__
	rm -rf tests/__pycache__
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Run example
run:
	poetry run python -c "from vault_file import VaultFile, VaultMetadata, VaultPayload; \
		vf = VaultFile(metadata=VaultMetadata(data={'test': 'example'}), payload=VaultPayload(data={'secret': 'value'})); \
		print(vf.to_json())"

# Run all checks
all: lint type-check test
