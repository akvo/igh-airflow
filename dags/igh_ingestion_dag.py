"""IGH Ingestion DAG - Syncs data from Microsoft Dataverse to Bronze database."""

import logging
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

logger = logging.getLogger(__name__)

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


def sync_dataverse(**context):
    """Placeholder sync function - replace with actual igh-data-sync implementation."""
    from pathlib import Path

    logger.info("Starting Dataverse sync...")

    # Ensure bronze directory exists
    bronze_dir = Path("/opt/airflow/data/bronze")
    bronze_dir.mkdir(parents=True, exist_ok=True)

    # Placeholder: actual sync would happen here
    # from igh_data_sync import run_sync
    # run_sync()

    logger.info("Placeholder: igh-data-sync would run here")
    logger.info("Sync completed at %s", datetime.now())

    return {"status": "success", "records_synced": 0}


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
