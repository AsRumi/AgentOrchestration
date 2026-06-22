.PHONY: help up down api worker init-db logs test

help:
	@echo "Conductor — Multi-Agent Orchestration System"
	@echo ""
	@echo "  make up          Start all services (Docker)"
	@echo "  make down        Stop all services"
	@echo "  make init-db     Create database tables"
	@echo "  make api         Run API server locally"
	@echo "  make worker      Run Celery worker locally"
	@echo "  make logs        Tail logs from all containers"
	@echo "  make test        Run tests"

up:
	docker compose up --build -d
	@echo "API running at http://localhost:8000"
	@echo "Flower (task monitor) at http://localhost:5555"
	@echo "API docs at http://localhost:8000/docs"

down:
	docker compose down

init-db:
	python -m src.db.init_db

api:
	uvicorn src.api.main:app --reload --port 8000

worker:
	celery -A src.workers.celery_app.celery_app worker --loglevel=info

logs:
	docker compose logs -f

test:
	pytest tests/ -v
