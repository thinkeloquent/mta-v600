# Hello FastAPI Makefile

.PHONY: help run run-dev test clean

help:
	@echo "Hello FastAPI Commands"
	@echo ""
	@echo "  make run      - Run production server"
	@echo "  make run-dev  - Run development server with reload"
	@echo "  make test     - Run tests"
	@echo "  make clean    - Clean Python cache"

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080

run-dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

test:
	pytest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
