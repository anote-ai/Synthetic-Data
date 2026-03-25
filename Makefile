.PHONY: install test lint dev frontend clean

install:
	cd server && pip install -r requirements.txt

install-dev:
	cd server && pip install -r requirements.txt && pip install pytest pytest-mock pytest-asyncio pytest-cov ruff

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
	rm -rf server/.coverage server/htmlcov server/outputs; \
	echo "Cleaned up"

outputs-clean:
	find outputs/ -type f -mtime +7 -delete 2>/dev/null; \
	echo "Removed output files older than 7 days"
