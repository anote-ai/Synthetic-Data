# Synthetic Data — Codebase Setup

Synthetic Data generates labeled text, image, audio, video, PII, tabular, code,
and multilingual datasets through a React frontend, Flask API, and Python SDK.

## Architecture

| Layer | Technology | Location | Default port |
| --- | --- | --- | --- |
| Frontend | React | `frontend/` | 3000 |
| Backend API | Flask + Gunicorn | `server/` | 5000 |
| Database | MySQL | Docker service `db` | 3306 |
| Job queue | Redis/RQ | Docker service `redis` | 6379 |

The historical `api/` and `other/` directories are not part of the supported
runtime. New API work belongs in `server/`.

## Docker setup

```bash
cp .env.example .env
# Set OPENAI_API_KEY and any provider tokens you need.
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:5000
- Health check: http://localhost:5000/health

## Manual setup

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

In another terminal:

```bash
cd frontend
npm ci
npm start
```

The frontend reads `REACT_APP_API_BASE_URL`. Because React injects this value at
build time, set it before running `npm run build`.

## Deployment

`.github/workflows/deploy.yml` builds `server/Dockerfile`, pushes the backend to
ECR/ECS, builds the frontend with `REACT_APP_API_BASE_URL`, and publishes the
static bundle to S3/CloudFront. Required secrets are listed in `README.md`.

## Verification

```bash
make test
cd frontend && npm test -- --watchAll=false
cd frontend && npm run build
docker compose config
```
