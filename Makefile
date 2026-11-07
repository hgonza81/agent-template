.DEFAULT_GOAL := help

.PHONY: help setup backend-env frontend-env frontend-deps db-up db-down migrate \
	migration backend backend-otel frontend test test-backend test-frontend check-backend \
	check-frontend test build audit format openapi api-types db-reset-test
.PHONY: observability-up observability-down

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  make %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create local .env files and install dependencies
	$(MAKE) backend-env
	cd backend && uv sync --frozen
	$(MAKE) frontend-env
	cd frontend && npm ci

backend-env: ## Create backend/.env from the example if it does not exist
	@if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; fi

frontend-env: ## Create frontend/.env from the example if it does not exist
	@if [ ! -f frontend/.env ]; then cp frontend/.env.example frontend/.env; fi

frontend-deps: frontend-env ## Install frontend dependencies if missing
	@if [ ! -d frontend/node_modules ]; then cd frontend && npm ci; fi

db-up: ## Start PostgreSQL in Docker and wait until it is ready
	docker compose up -d --wait postgres

db-down: ## Stop containers without deleting data
	docker compose down

migrate: backend-env db-up ## Apply migrations to the development database
	cd backend && uv run alembic upgrade head

migration: backend-env db-up ## Create a migration: make migration MESSAGE="describe change"
	@test -n "$(MESSAGE)" || (echo 'Usage: make migration MESSAGE="describe change"' >&2; exit 2)
	cd backend && uv run alembic revision --autogenerate -m "$(MESSAGE)"

backend: migrate ## Start the API (starts PostgreSQL and applies migrations)
	cd backend && uv run uvicorn agent_template_api.main:app --reload --no-access-log

backend-otel: migrate observability-up ## Start the API with local traces and metrics enabled
	cd backend && OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318 \
		uv run uvicorn agent_template_api.main:app --reload --no-access-log

observability-up: ## Start the optional local OTLP collector and viewers
	docker compose --profile observability up -d --wait otel-collector prometheus jaeger

observability-down: ## Stop the optional local telemetry services
	docker compose --profile observability stop otel-collector prometheus jaeger

frontend: frontend-env frontend-deps ## Start the frontend
	cd frontend && npm run dev

test-backend: backend-env db-up ## Run backend tests against the test database
	cd backend && uv run pytest

test-frontend: frontend-deps ## Run frontend tests
	cd frontend && npm test

test: test-backend test-frontend ## Run all tests

check-backend: backend-env ## Check backend formatting, lint, and types
	cd backend && uv run ruff format --check .
	cd backend && uv run ruff check .
	cd backend && uv run mypy src tests

check-frontend: frontend-deps ## Run frontend lint, type checks, and build
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm run build

build: check-frontend ## Build the frontend for production

check: check-backend test check-frontend ## Run all project checks and tests

audit: backend-env frontend-deps ## Audit Python and npm dependencies
	@requirements_file=$$(mktemp); \
	trap 'rm -f "$$requirements_file"' EXIT; \
	cd backend && uv export --locked --format requirements.txt --no-emit-project \
		--output-file "$$requirements_file" && \
	uv run pip-audit --strict --require-hashes --requirement "$$requirements_file"
	cd frontend && npm audit --audit-level=low

format: backend-env ## Format Python code
	cd backend && uv run ruff format .

openapi: backend-env ## Update the OpenAPI contract
	cd backend && uv run python -m agent_template_api.export_openapi

api-types: openapi frontend-deps ## Update the OpenAPI contract and frontend types
	cd frontend && npm run generate:api

db-reset-test: db-up ## Recreate ONLY agent_template_test and apply its migrations
	docker compose exec -T postgres dropdb --if-exists -U agent_template agent_template_test
	docker compose exec -T postgres createdb -U agent_template --owner=agent_template agent_template_test
	cd backend && DATABASE_URL=postgresql+psycopg://agent_template:local-dev-only@127.0.0.1:5433/agent_template_test \
		uv run alembic upgrade head
