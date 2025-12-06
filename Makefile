# MTA-v600 Makefile
# Development commands for the monorepo

# Default ports
FASTIFY_PORT ?= 51000
FASTAPI_PORT ?= 52000

.PHONY: help install dev dev-frontend dev-fastify dev-fastapi build test lint format clean docker-up docker-down

help:
	@echo "MTA-v600 Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       - Install all dependencies (pnpm + poetry)"
	@echo ""
	@echo "Development:"
	@echo "  make dev           - Run frontend (watch) + all backends"
	@echo "  make dev-frontend  - Run frontend build in watch mode"
	@echo "  make dev-fastify   - Run Fastify backend only (port 51000)"
	@echo "  make dev-fastapi   - Run FastAPI backend only (port 52000)"
	@echo ""
	@echo "Build:"
	@echo "  make build         - Build all projects (frontend + backends)"
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

# Development - run frontend watch + all backends in parallel
dev:
	@echo "Starting development servers..."
	@echo "  Frontend: watch mode (rebuilds on changes)"
	@echo "  Fastify:  http://localhost:$(FASTIFY_PORT)"
	@echo "  FastAPI:  http://localhost:$(FASTAPI_PORT)"
	@echo ""
	@$(MAKE) -j3 dev-frontend dev-fastify dev-fastapi

# Run frontend build in watch mode
dev-frontend:
	cd frontend-apps/main-entry && pnpm dev

# Run Fastify backend
dev-fastify:
	cd fastify-apps/main-entry && PORT=$(FASTIFY_PORT) node server.test.mjs

# Run FastAPI backend
dev-fastapi:
	cd fastapi-apps/main-entry && uvicorn app.main:app --reload --host 0.0.0.0 --port $(FASTAPI_PORT)

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
