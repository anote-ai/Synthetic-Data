# Synthetic Data — Codebase Setup

## What is Synthetic Data?

Synthetic Data is a tool for generating synthetic datasets, available at [anote.ai/syntheticdata](https://anote.ai/syntheticdata). It lets you create high-quality labeled training data from scratch using LLMs.

## Architecture

| Layer | Technology | Location |
|-------|-----------|----------|
| Frontend | React (Create React App) | `frontend/` |
| Backend API | Python, FastAPI | `api/` |
| Backend workers / utilities | Python | `server/` |
| Container orchestration | Docker Compose | `docker-compose.yml` + `docker-compose.override.yml` (local dev) |

The `docker-compose.override.yml` file is automatically picked up by Docker Compose for local development and adds volume mounts and hot-reload settings on top of the base `docker-compose.yml`.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (recommended path)
- Node 18+ (manual frontend setup)
- Python 3.11+ (manual backend setup)

## Quick Start with Docker Compose (RECOMMENDED)

```bash
# 1. Clone the repo
git clone https://github.com/anote-ai/Synthetic-Data.git
cd Synthetic-Data

# 2. Copy the example env file and fill in your values
cp .env.example .env

# 3. Start all services (override file is applied automatically)
docker-compose up --build
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8000](http://localhost:8000)

## Manual Setup (without Docker)

### Backend (API)

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start   # starts on http://localhost:3000
```

## Environment Variables

All environment variables are documented in `.env.example`. Key variables include:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key used for synthetic generation |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude-based generation |
| `DATABASE_URL` | PostgreSQL connection string |
| `REACT_APP_BACK_END_HOST` | Backend URL consumed by the React app |

## CI / CD

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `ci.yml` | Pull request | Runs lint and tests on every PR |
| `publish.yml` | Push to `main` / tag | Publishes the Python package to PyPI |
| `deploy.yml` | Manual (`workflow_dispatch`) | Builds Docker image (ECR repository: `synthetic-data-backend`) → pushes to ECR → updates ECS; syncs frontend to S3, invalidates CloudFront |

### Required GitHub Secrets for Deployment

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM access key with ECS/ECR/S3/CloudFront permissions |
| `AWS_SECRET_ACCESS_KEY` | Corresponding IAM secret |
| `AWS_REGION` | AWS region, e.g. `us-east-1` |
| `ECS_CLUSTER` | Name of the ECS cluster |
| `ECS_SERVICE_BACKEND` | Name of the ECS service for the backend |
| `S3_BUCKET_FRONTEND` | S3 bucket name for the frontend static files |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID to invalidate after deploy |
| `REACT_APP_BACK_END_HOST` | Backend URL injected at React build time |
| `SLACK_WEBHOOK_URL` | (Optional) Slack incoming webhook for failure notifications |
