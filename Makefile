.PHONY: install up down migrate test lint format run worker

install:
	python -m venv .venv && .venv/bin/pip install -r requirements/dev.txt

up:
	docker compose up --build -d

down:
	docker compose down

migrate:
	python manage.py migrate

run:
	python manage.py runserver

worker:
	celery -A config worker -l info

test:
	pytest

lint:
	ruff check . && ruff format --check .

format:
	ruff format . && ruff check --fix .
