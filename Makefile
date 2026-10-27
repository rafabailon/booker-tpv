HOST_UID ?= $(shell id -u)
HOST_GID ?= $(shell id -g)

.PHONY: up down build logs ps test test-backend test-frontend lint format clean purge dev migrate bootstrap frontend-lock

up: frontend-lock
	docker compose up --build -d

dev: frontend-lock
	docker compose -f compose.yaml -f compose.dev.yaml --profile dev up --build

down:
	docker compose down

build: frontend-lock
	docker compose build

frontend-lock:
	HOST_UID=$(HOST_UID) HOST_GID=$(HOST_GID) docker compose --profile tools run --rm frontend-lock

logs:
	docker compose logs -f

ps:
	docker compose ps

migrate:
	docker compose --profile tools run --rm migrate

bootstrap:
	docker compose run --rm api python -m app.bootstrap_admin

test: test-backend test-frontend

test-backend:
	@set -e; trap 'docker compose --profile test stop test-db >/dev/null 2>&1 || true' EXIT; \
		docker compose --profile test run --build --rm backend-tests

test-frontend: frontend-lock
	docker compose --profile test run --build --rm --no-deps frontend-tests

lint: frontend-lock
	docker compose --profile test run --build --rm --no-deps backend-tests ruff check app tests
	docker compose --profile test run --build --rm --no-deps frontend-tests npm run lint

format:
	docker compose --profile test run --build --rm --no-deps backend-tests ruff format app tests

clean:
	docker compose --profile dev --profile test --profile tools down --remove-orphans

purge:
	@printf '%s\n' 'This removes this project'\''s containers and PostgreSQL volume.'; \
		docker compose --profile dev --profile test --profile tools down --volumes --remove-orphans
