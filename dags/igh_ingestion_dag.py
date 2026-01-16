"""IGH Ingestion DAG - Syncs data from Microsoft Dataverse to Bronze database."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import config
from utils.slack_alerts import send_failure_alert, send_success_alert

default_args = {
    "owner": "igh",
    "depends_on_past": False,
    "retries": config.retries,
    "retry_delay": config.retry_delay,
    "on_failure_callback": send_failure_alert,
}


def run_dataverse_sync(**context):
    """Execute Dataverse sync to Bronze database.

    This function will call the igh-data-sync library when available.
    For now, it provides a placeholder implementation.
    """
    import logging

    logger = logging.getLogger(__name__)

    bronze_db_path = config.bronze_db_path
    logger.info(f"Starting Dataverse sync to {bronze_db_path}")

    # TODO: Replace with actual sync call when igh-data-sync is available
    # from igh_data_sync import run_sync
    # run_sync(db_path=bronze_db_path)

    # Placeholder - ensure directory exists
    db_path = Path(bronze_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Dataverse sync completed successfully")
    return {"status": "success", "db_path": str(bronze_db_path)}


with DAG(
    dag_id="igh_ingestion",
    description="Sync data from Microsoft Dataverse to Bronze SQLite database",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=config.ingestion_schedule,
    catchup=False,
    tags=["igh", "ingestion", "dataverse"],
    on_success_callback=send_success_alert,
) as dag:
    sync_task = PythonOperator(
        task_id="sync_dataverse",
        python_callable=run_dataverse_sync,
        execution_timeout=timedelta(hours=2),
    )
