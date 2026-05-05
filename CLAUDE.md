# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

This is an Apache Airflow 3.1.6 orchestration project for the IGH Data Pipeline using CeleryExecutor. It manages three main workflows:
- **Ingestion**: Sync data from Microsoft Dataverse to Bronze SQLite database
- **Transform**: Process data from Bronze to Silver and Gold layers
- **Deployment**: Deploy validated data to production

## Development Commands

### Environment Setup

```bash
# Install dependencies with UV
uv sync

# Install with dev dependencies
uv sync --all-groups
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_ingestion_dag.py -v

# Run with coverage
uv run pytest tests/ --cov=dags --cov=config
```

### Linting

```bash
# Check code style
uv run ruff check dags/ config/ tests/

# Auto-fix issues
uv run ruff check --fix dags/ config/ tests/

# Format code
uv run ruff format dags/ config/ tests/
```

### Local Development with Docker

```bash
# Start Airflow (builds custom image)
docker compose up -d

# Force rebuild image
docker compose build --no-cache

# View logs
docker compose logs -f

# Access shell
docker compose exec airflow-apiserver bash

# List DAGs
docker compose exec airflow-apiserver airflow dags list

# Stop Airflow
docker compose down

# Run with Flower (Celery monitoring)
docker compose --profile flower up -d
```

## Architecture

### DAG Pipeline

All DAGs are manual-trigger only — no schedules, no cross-DAG triggers.

```
igh_ingestion (manual only)
    └── sync_dataverse

igh_transform (manual only)
    ├── bronze_to_silver
    └── silver_to_gold

igh_deployment (manual only)
    ├── scp_gold_db
    └── swap_remote_db
```

### Project Structure

```
igh-airflow/
├── dags/                    # Airflow DAG definitions
│   ├── igh_ingestion_dag.py # Dataverse sync using igh-data-sync
│   ├── igh_transform_dag.py # Bronze→Silver→Gold
│   └── igh_deployment_dag.py # Production deployment
├── config/                  # Configuration modules
│   └── settings.py          # PipelineConfig dataclass
├── data/                    # Data directories (bronze/silver/production)
├── logs/                    # Airflow logs
├── tests/                   # Unit tests
├── docker/                  # Production Docker files
│   ├── Dockerfile           # Airflow 3.1.6 + igh-data-sync
│   └── entrypoint.sh        # Custom entrypoint
├── docker-compose.yml       # Local development (CeleryExecutor)
└── pyproject.toml           # Project configuration
```

### Key Modules

- **config/settings.py**: Centralized configuration with `PipelineConfig` dataclass. Uses `get_env()` to read from environment variables with fallback to Airflow Variables.
- **dags/igh_ingestion_dag.py**: Uses `igh-data-sync` library to sync from Dataverse. Exposes a boolean DAG param `update_mode` (default `False`). When `False` the task deletes the existing bronze DB before syncing (fresh build, matching `sync-and-run-etl.sh`); when `True` it keeps the bronze DB and syncs incrementally.

## Configuration

### Environment Variables (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `AIRFLOW_IMAGE_NAME` | Docker image name | `igh-airflow:latest` |
| `AIRFLOW_UID` | Linux user ID for Airflow | `50000` |
| `REDIS_PASSWORD` | Redis password for Celery broker | `redispass` |
| `_AIRFLOW_WWW_USER_USERNAME` | Airflow UI username | `airflow` |
| `_AIRFLOW_WWW_USER_PASSWORD` | Airflow UI password | `airflow` |
| `AIRFLOW__CORE__FERNET_KEY` | Fernet encryption key | - |
| `AIRFLOW__API__SECRET_KEY` | API secret key for JWT | - |
| `BRONZE_DB_PATH` | Bronze database location | `/opt/airflow/data/bronze/dataverse.db` |
| `SILVER_DB_PATH` | Silver database location | `/opt/airflow/data/silver/igh_silver.db` |
| `GOLD_DB_PATH` | Gold star-schema database location | `/opt/airflow/data/gold/star_schema.db` |
| `DEPLOY_SSH_KEY_PATH` | SSH private key path inside container | `/opt/airflow/ssh/id_rsa` |
| `DEPLOY_TARGET_HOST` | Dashboard server host (`local` or empty to skip) | `local` (dev compose) |
| `DEPLOY_TARGET_USER` | SSH user on dashboard server | - |
| `DEPLOY_TARGET_PATH` | Remote path for `star_schema.db` | - |
| `DEPLOY_SSH_KEY_PATH_HOST` | Host path to SSH key (Docker mount, self-hosted only) | `./ssh/id_rsa` |
| `DATAVERSE_API_URL` | Dataverse API endpoint URL | - |
| `DATAVERSE_CLIENT_ID` | OAuth client ID | - |
| `DATAVERSE_CLIENT_SECRET` | OAuth client secret | - |
| `DATAVERSE_SCOPE` | OAuth scope | - |

### Generating Security Keys

```bash
# Generate Fernet key
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate API secret key
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

### Airflow Variables (Admin → Variables)

Airflow Variables are used as fallback when environment variables are not set:

| Variable | Description |
|----------|-------------|
| `DATAVERSE_API_URL` | Fallback for Dataverse API endpoint URL |
| `DATAVERSE_CLIENT_ID` | Fallback for OAuth client ID |
| `DATAVERSE_CLIENT_SECRET` | Fallback for OAuth client secret |
| `DATAVERSE_SCOPE` | Fallback for OAuth scope |

## Testing

Tests verify DAG structure, task counts, and dependencies without running actual tasks.

```bash
# All tests should pass
uv run pytest tests/ -v
```

## Common Tasks

### Adding a New DAG

1. Create `dags/new_dag.py` following existing patterns
2. Add tests in `tests/test_new_dag.py`
3. Run tests: `uv run pytest tests/test_new_dag.py -v`

### Modifying Configuration

1. Update `config/settings.py` for new settings
2. Update `.env.example` for new environment variables
3. Update this CLAUDE.md with new variables

### Debugging DAG Issues

1. Check Airflow logs: `docker compose logs airflow-scheduler`
2. List DAGs: `docker compose exec airflow-apiserver airflow dags list`
3. Test DAG loading: `docker compose exec airflow-apiserver python -c "from dags.igh_ingestion_dag import dag; print(dag)"`
4. Check Celery workers: `docker compose logs airflow-worker`
5. Monitor Celery with Flower: `docker compose --profile flower up -d` then visit http://localhost:5555

## Troubleshooting

### Redis/Celery Compatibility

The project pins `redis>=5.0.0,<6.0.0` in `pyproject.toml` due to compatibility issues between `redis 6.x` and `kombu` (Celery's transport library). If you see errors like:

```
AttributeError: module 'redis' has no attribute 'client'
```

Ensure the redis package is pinned to version 5.x and rebuild the Docker image:

```bash
docker compose build --no-cache && docker compose up -d
```
