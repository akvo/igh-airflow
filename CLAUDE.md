# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

This is an Apache Airflow orchestration project for the IGH Data Pipeline. It manages three main workflows:
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
uv run pytest tests/ --cov=dags --cov=utils --cov=config
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

### Local Development with Docker

```bash
# Start Airflow
docker compose up -d

# View logs
docker compose logs -f

# Access shell
docker compose exec airflow-apiserver bash

# List DAGs
docker compose exec airflow-apiserver airflow dags list

# Stop Airflow
docker compose down
```

## Architecture

### DAG Pipeline

```
igh_ingestion (02:00 daily)
    └── sync_dataverse
            ↓
igh_transform (04:00 daily)
    ├── wait_for_ingestion (ExternalTaskSensor)
    ├── bronze_to_silver
    └── silver_to_gold
            ↓
igh_deployment (06:00 daily)
    ├── wait_for_transform (ExternalTaskSensor)
    ├── verify_silver_database
    ├── deploy_to_production
    └── verify_production_database
```

### Project Structure

```
igh-airflow/
├── dags/                    # Airflow DAG definitions
│   ├── igh_ingestion_dag.py # Dataverse sync
│   ├── igh_transform_dag.py # Bronze→Silver→Gold
│   └── igh_deployment_dag.py # Production deployment
├── config/                  # Configuration modules
│   └── settings.py          # PipelineConfig dataclass
├── utils/                   # Utility functions
│   └── slack_alerts.py      # Slack notifications
├── tests/                   # Unit tests
├── docker/                  # Production Docker files
├── docker-compose.yml       # Local development
└── pyproject.toml           # Project configuration
```

### Key Modules

- **config/settings.py**: Centralized configuration with `PipelineConfig` dataclass
- **utils/slack_alerts.py**: Slack webhook notifications for failures/success
- **dags/**: Three DAGs with ExternalTaskSensor dependencies

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BRONZE_DB_PATH` | Bronze database location | `/opt/airflow/data/bronze/dataverse.db` |
| `SILVER_DB_PATH` | Silver database location | `/opt/airflow/data/silver/igh_silver.db` |
| `PRODUCTION_DB_PATH` | Production database location | `/opt/airflow/data/production/igh.db` |
| `SLACK_WEBHOOK_URL` | Slack webhook for alerts | - |
| `INGESTION_SCHEDULE` | Cron schedule for ingestion | `0 2 * * *` |
| `TRANSFORM_SCHEDULE` | Cron schedule for transform | `0 4 * * *` |
| `DEPLOYMENT_SCHEDULE` | Cron schedule for deployment | `0 6 * * *` |

### Airflow Connections (Manual Setup)

| Connection ID | Type | Purpose |
|--------------|------|---------|
| `dataverse_api` | HTTP | Dataverse API authentication |
| `slack_webhook` | Slack Webhook | Slack notifications |

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
