# IGH Airflow

Apache Airflow orchestration for the IGH Data Pipeline.

## Overview

This project provides Airflow DAGs to orchestrate the IGH data pipeline:

- **Ingestion**: Sync data from Microsoft Dataverse to Bronze SQLite database
- **Transform**: Process data from Bronze to Silver and Gold layers
- **Deployment**: Deploy validated data to production

## Quick Start

```bash
# Install dependencies with UV
uv sync

# Install with dev dependencies
uv sync --all-groups

# Start local Airflow environment
docker compose up -d

# Access Airflow UI at http://localhost:8080
# Default credentials: airflow / airflow
```

## Project Structure

```
igh-airflow/
├── dags/           # Airflow DAG definitions
├── plugins/        # Custom Airflow plugins
├── config/         # Configuration modules
├── utils/          # Utility functions
├── tests/          # Unit tests
└── docker/         # Production Docker files
```
