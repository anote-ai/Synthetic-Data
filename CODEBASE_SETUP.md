# Synthetic Data — Codebase Setup

## What is Synthetic Data?

Synthetic Data is a platform for generating synthetic datasets at [anote.ai/syntheticdata](https://anote.ai/syntheticdata). It enables teams to create high-quality labeled training data at scale using LLMs, reducing the cost and time of manual annotation.

## Architecture

| Layer | Technology | Location |
|-------|-----------|----------|
| Frontend | React (Node 18) | `frontend/` |
| API / Backend | Python, FastAPI | `api/` |
| Server utilities | Python | `server/` |
| Container orchestration | Docker Compose | `docker-compose.yml` + `docker-compose.override.yml` |

`docker-compose.override.yml` is used for local development overrides (e.g. volume mounts, hot reload) and is applied automatically when running `docker-compose up`.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (v2+)
- Node 18 (only needed for manual frontend setup)
- Python 3.11 (only needed for manual backend setup)

## Quick Start with Docker Compose (RECOMMENDED)

```bash
# 1. Clone the repo
git clone https://github.com/anote-ai/Synthetic-Data.git
cd Synthetic-Data

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env and set required values (see Environment Variables below)

# 3. Start all services (override file is picked up automatically)
docker-compose up --build
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- API: [http://localhost:8000](http://localhost:8000)

## Manual Setup (without Docker)

### Backend (api/)

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start
```

The dev server starts at `http://localhost:3000`.

## Environment Variables

Copy `.env.example` to `.env`. Key variables include:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for synthetic generation |
| `ANTHROPIC_API_KEY` | No | Anthropic API key for Claude models |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | Random secret for session tokens |
| `REACT_APP_BACK_END_HOST` | Yes | Backend URL seen by the browser |

Refer to `.env.example` for the full list of variables and their defaults.

## CI/CD

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `ci.yml` | PR / push to main | Runs lint and tests on PRs |
| `publish.yml` | Tag / release | Publishes the Python package to PyPI |
| `deploy.yml` | Manual (`workflow_dispatch`) | Builds Docker image → ECR → ECS (backend); React build → S3 → CloudFront (frontend) |

### Required GitHub Secrets for Deployment

Configure these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM access key with ECR/ECS/S3/CloudFront permissions |
| `AWS_SECRET_ACCESS_KEY` | Corresponding IAM secret key |
| `AWS_REGION` | AWS region (defaults to `us-east-1`) |
| `ECS_CLUSTER` | ECS cluster name |
| `ECS_SERVICE_BACKEND` | ECS service name (ECR repository: `synthetic-data-backend`) |
| `S3_BUCKET_FRONTEND` | S3 bucket for the React build |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID |
| `REACT_APP_BACK_END_HOST` | Backend URL injected at React build time |
| `SLACK_WEBHOOK_URL` | (Optional) Slack webhook for failure alerts |
