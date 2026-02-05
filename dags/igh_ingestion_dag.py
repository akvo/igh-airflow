"""IGH Ingestion DAG - Syncs data from Microsoft Dataverse to Bronze database."""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.providers.standard.operators.python import PythonOperator

# Import utilities
sys.path.insert(0, "/opt/airflow")
from utils.slack_alerts import send_failure_alert  # noqa: E402

default_args = {
    "owner": "igh",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": send_failure_alert,
}

# Get schedule from environment variable with default
INGESTION_SCHEDULE = os.environ.get("INGESTION_SCHEDULE", "0 2 * * *")

logger = logging.getLogger(__name__)


def get_env_or_variable(key: str, default: str | None = None) -> str:
    """Get value from environment variable, falling back to Airflow Variable."""
    value = os.environ.get(key)
    if value:
        return value
    try:
        return Variable.get(key, default_var=default)
    except Exception:
        if default is not None:
            return default
        raise


def sync_dataverse(**context):
    """Sync data from Microsoft Dataverse to Bronze SQLite database using igh-data-sync."""
    from pathlib import Path

    from igh_data_sync import run_sync
    from igh_data_sync.config import Config

    logger.info("Starting Dataverse sync...")

    # Get database path from environment
    bronze_db_path = get_env_or_variable(
        "BRONZE_DB_PATH", "/opt/airflow/data/bronze/dataverse.db"
    )

    # Ensure bronze directory exists
    bronze_dir = Path(bronze_db_path).parent
    bronze_dir.mkdir(parents=True, exist_ok=True)

    # Build config from environment variables (with Airflow Variable fallback)
    config = Config(
        api_url=get_env_or_variable("DATAVERSE_API_URL"),
        client_id=get_env_or_variable("DATAVERSE_CLIENT_ID"),
        client_secret=get_env_or_variable("DATAVERSE_CLIENT_SECRET"),
        scope=get_env_or_variable("DATAVERSE_SCOPE"),
        sqlite_db_path=bronze_db_path,
    )

    logger.info("Syncing to database: %s", bronze_db_path)

    # Run async sync function
    success = asyncio.run(
        run_sync(
            config=config,
            verify_reference=False,
            logger=logger,
        )
    )

    if not success:
        raise RuntimeError("Dataverse sync failed - check logs for details")

    logger.info("Sync completed successfully at %s", datetime.now())

    return {"status": "success", "database": bronze_db_path}


with DAG(
    dag_id="igh_ingestion",
    description="Sync data from Microsoft Dataverse to Bronze SQLite database",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=INGESTION_SCHEDULE,
    catchup=False,
    tags=["igh", "ingestion", "dataverse"],
) as dag:
    sync_task = PythonOperator(
        task_id="sync_dataverse",
        python_callable=sync_dataverse,
        execution_timeout=timedelta(hours=2),
    )
