# MTA-v600 Makefile
# Development commands for the monorepo

.PHONY: help install dev apps build test lint format clean docker-up docker-down

help:
	@echo "MTA-v600 Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       - Install all dependencies (pnpm + poetry)"
	@echo ""
	@echo "Development:"
	@echo "  make dev           - Run frontend dev servers only"
	@echo "  make apps NAME=... - Run backend server (e.g., NAME=@internal/fastify-hello-fastify)"
	@echo "  make dev-fastapi   - Run FastAPI backend server"
	@echo ""
	@echo "Build:"
	@echo "  make build         - Build all projects"
	@echo "  make test          - Run all tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          - Lint all code"
	@echo "  make format        - Format all code"
	@echo "  make check         - Run all checks"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up     - Start database services"
	@echo "  make docker-down   - Stop database services"
	@echo ""
	@echo "Clean:"
	@echo "  make clean         - Clean build artifacts"

# Setup
install:
	pnpm install
	poetry install --no-root

# Development - frontends only
dev:
	pnpm dev

# Run backend server by name
# Usage: make apps NAME=@internal/fastify-hello-fastify
apps:
ifndef NAME
	@echo "Usage: make apps NAME=<project-name>"
	@echo "Example: make apps NAME=@internal/fastify-hello-fastify"
	@exit 1
endif
	nx serve $(NAME)

dev-fastapi:
	cd fastapi-apps/hello-fastapi && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Build
build:
	pnpm build

test:
	pnpm test

# Code Quality
lint:
	pnpm lint

format:
	pnpm format

check:
	pnpm check

# Docker
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

# Clean
clean:
	pnpm clean
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
