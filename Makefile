.PHONY: dev test test-unit test-integration lint format format-check docker-up docker-down openapi

dev:                ## Start development server
	uv run main.py

test:               ## Run all tests
	uv run pytest

test-unit:          ## Run unit tests only
	uv run pytest tests/unit/

test-integration:   ## Run integration tests only
	uv run pytest tests/integration/

lint:               ## Run ruff linter
	uv run ruff check

format:             ## Auto-format with ruff
	uv run ruff format

format-check:       ## Check formatting without changes (CI)
	uv run ruff format --check

docker-up:          ## Start full stack (MongoDB + Redis + app)
	docker-compose up -d

docker-down:        ## Stop full stack
	docker-compose down

openapi:            ## Export OpenAPI spec to openapi.json
	uv run python -c \
		"from app import create_app; import json; app = create_app(); \
		print(json.dumps(app.spec, indent=2))" > openapi.json

docs:               ## Open API docs in browser (requires running server)
	open http://localhost:8000/docs
