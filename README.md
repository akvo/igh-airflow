# IGH Airflow

Apache Airflow orchestration for the IGH Data Pipeline.

## Overview

This project provides Airflow DAGs to orchestrate the IGH data pipeline:

- **Ingestion**: Sync data from Microsoft Dataverse to Bronze SQLite database
- **Transform**: Process data from Bronze to Silver and Gold layers
- **Deployment**: Deploy validated data to production

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for development)
- UV (for dependency management)

### Local Development

```bash
# Clone the repository
git clone <repository-url>
cd igh-airflow

# Copy environment template
cp .env.example .env

# Install dependencies first
uv sync

# Generate security keys
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add output to AIRFLOW__CORE__FERNET_KEY in .env

uv run python -c "import secrets; print(secrets.token_hex(32))"
# Add output to AIRFLOW__WEBSERVER__SECRET_KEY in .env

# Set your user ID (Linux only)
echo "AIRFLOW_UID=$(id -u)" >> .env

# Start Airflow
docker compose up -d

# Access Airflow UI at http://localhost:8080
# Default credentials: airflow / airflow
```

## Architecture

### Pipeline Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   igh_ingestion │───▶│  igh_transform  │───▶│ igh_deployment  │
│   (02:00 UTC)   │    │   (04:00 UTC)   │    │   (06:00 UTC)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                      │                      │
        ▼                      ▼                      ▼
   Dataverse            Bronze → Silver        Silver → Production
   → Bronze             Silver → Gold          (atomic swap)
```

### DAG Details

| DAG | Schedule | Tasks | Description |
|-----|----------|-------|-------------|
| `igh_ingestion` | `0 2 * * *` | 1 | Sync Dataverse to Bronze DB |
| `igh_transform` | `0 4 * * *` | 3 | Transform Bronze→Silver→Gold |
| `igh_deployment` | `0 6 * * *` | 4 | Deploy to production with verification |

## Project Structure

```
igh-airflow/
├── dags/
│   ├── __init__.py
│   ├── igh_ingestion_dag.py    # Dataverse sync
│   ├── igh_transform_dag.py    # Bronze→Silver→Gold transforms
│   └── igh_deployment_dag.py   # Production deployment
├── plugins/
│   └── __init__.py
├── config/
│   ├── __init__.py
│   └── settings.py             # PipelineConfig dataclass
├── utils/
│   ├── __init__.py
│   └── slack_alerts.py         # Slack notification helpers
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_ingestion_dag.py
│   ├── test_transform_dag.py
│   ├── test_deployment_dag.py
│   └── test_slack_alerts.py
├── docker/
│   ├── Dockerfile              # Production image
│   └── entrypoint.sh
├── docker-compose.yml          # Local development
├── .env.example
├── .gitignore
├── .python-version
├── CLAUDE.md
├── pyproject.toml
└── README.md
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AIRFLOW_UID` | `50000` | User ID for Airflow processes |
| `BRONZE_DB_PATH` | `/opt/airflow/data/bronze/dataverse.db` | Bronze database path |
| `SILVER_DB_PATH` | `/opt/airflow/data/silver/igh_silver.db` | Silver database path |
| `PRODUCTION_DB_PATH` | `/opt/airflow/data/production/igh.db` | Production database path |
| `SLACK_WEBHOOK_URL` | - | Slack webhook for alerts |
| `INGESTION_SCHEDULE` | `0 2 * * *` | Ingestion cron schedule |
| `TRANSFORM_SCHEDULE` | `0 4 * * *` | Transform cron schedule |
| `DEPLOYMENT_SCHEDULE` | `0 6 * * *` | Deployment cron schedule |

### Airflow Connections

Configure these in the Airflow UI (Admin → Connections):

| Connection ID | Type | Fields |
|--------------|------|--------|
| `dataverse_api` | HTTP | Host: API URL, Login: Client ID, Password: Client Secret |
| `slack_webhook` | Slack Webhook | Password: Webhook path |

### Airflow Variables

Configure these in the Airflow UI (Admin → Variables):

| Variable | Default | Description |
|----------|---------|-------------|
| `bronze_db_path` | `/data/bronze/dataverse.db` | Bronze database path |
| `silver_db_path` | `/data/silver/igh_silver.db` | Silver database path |
| `production_db_path` | `/data/production/igh.db` | Production database path |

## Development

### Install Dependencies

```bash
# Install UV if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Install with dev dependencies
uv sync --all-groups
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=dags --cov=utils --cov=config

# Run specific test file
uv run pytest tests/test_ingestion_dag.py -v
```

### Linting

```bash
# Check code style
uv run ruff check dags/ utils/ config/ tests/

# Auto-fix issues
uv run ruff check --fix dags/ utils/ config/ tests/

# Format code
uv run ruff format dags/ utils/ config/ tests/
```

### Docker Commands

```bash
# Start Airflow
docker compose up -d

# View logs
docker compose logs -f airflow-scheduler

# Access Airflow shell
docker compose exec airflow-webserver bash

# List DAGs
docker compose exec airflow-webserver airflow dags list

# Trigger DAG manually
docker compose exec airflow-webserver airflow dags trigger igh_ingestion

# Stop Airflow
docker compose down

# Stop and remove volumes
docker compose down -v
```

## Production Deployment

### Build Production Image

```bash
docker build -f docker/Dockerfile -t igh-airflow:latest .
```

### Run Production Container

```bash
docker run -d \
  -e AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://... \
  -e AIRFLOW__CORE__FERNET_KEY=... \
  -e AIRFLOW__WEBSERVER__SECRET_KEY=... \
  -v /data:/opt/airflow/data \
  igh-airflow:latest webserver
```

## Alerts

The pipeline sends Slack notifications on:
- Task failures (with error details)
- DAG completion (success notification)

Configure `SLACK_WEBHOOK_URL` in your `.env` file or as an Airflow Variable.

## License

Copyright Akvo Foundation
