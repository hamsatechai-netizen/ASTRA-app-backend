.PHONY: install install-dev run dev test lint format typecheck migrate migrate-generate docker-build docker-up docker-down

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest -v --cov=app --cov-report=term-missing

lint:
	ruff check app tests

format:
	black app tests
	ruff check --fix app tests

typecheck:
	mypy app

migrate:
	alembic upgrade head

migrate-generate:
	alembic revision --autogenerate -m "$(m)"

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
