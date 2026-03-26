.PHONY: install install-dev test test-cov lint dev frontend clean docker-up docker-down docker-logs docker-build

# ── Local development ──────────────────────────────────────────

install:
	cd server && pip install -r requirements.txt

install-dev:
	cd server && pip install -r requirements.txt && pip install pytest pytest-mock pytest-asyncio pytest-cov ruff responses

test:
	cd server && pytest tests/ -v --tb=short

test-cov:
	cd server && pytest tests/ -v --tb=short --cov=. --cov-report=term-missing --cov-report=html

lint:
	cd server && ruff check . --ignore E501,F401

dev:
	cd server && python app.py

frontend:
	cd frontend && npm start

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type f -name "*.pyc" -delete 2>/dev/null; \
	rm -rf server/.coverage server/htmlcov; \
	echo "Cleaned up"

# ── Docker ─────────────────────────────────────────────────────

docker-build:
	docker compose build

docker-up:
	docker compose up -d
	@echo "API: http://localhost:5000"
	@echo "Frontend: http://localhost:3000"

docker-up-db:
	docker compose --profile db up -d
	@echo "API: http://localhost:5000 | DB: localhost:3306"

docker-down:
	docker compose down

docker-down-volumes:
	docker compose down -v

docker-logs:
	docker compose logs -f api

docker-restart:
	docker compose restart api

docker-shell:
	docker compose exec api /bin/bash
