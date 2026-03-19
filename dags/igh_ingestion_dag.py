"""IGH Ingestion DAG - Syncs data from Microsoft Dataverse to Bronze database."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import config, get_env
from utils.slack_alerts import send_failure_alert

default_args = {
    "owner": "igh",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": send_failure_alert,
}

logger = logging.getLogger(__name__)


def sync_dataverse(**context):
    """Sync data from Microsoft Dataverse to Bronze SQLite database using igh-data-sync."""
    from igh_data_sync import run_sync
    from igh_data_sync.config import Config

    logger.info("Starting Dataverse sync...")

    # Ensure bronze directory exists
    bronze_path = Path(config.bronze_db_path)
    bronze_path.parent.mkdir(parents=True, exist_ok=True)

    # Build config from environment variables (with Airflow Variable fallback)
    # Dataverse credentials are sensitive and fetched via get_env, not in PipelineConfig
    config_obj = Config(
        api_url=get_env("DATAVERSE_API_URL", ""),
        client_id=get_env("DATAVERSE_CLIENT_ID", ""),
        client_secret=get_env("DATAVERSE_CLIENT_SECRET", ""),
        scope=get_env("DATAVERSE_SCOPE", ""),
        sqlite_db_path=config.bronze_db_path,
    )

    logger.info("Syncing to database: %s", config.bronze_db_path)

    # Run async sync function
    success = asyncio.run(
        run_sync(
            config=config_obj,
            verify_reference=False,
            logger=logger,
        )
    )

    if not success:
        raise RuntimeError("Dataverse sync failed - check logs for details")

    logger.info("Sync completed successfully at %s", datetime.now())

    return {"status": "success", "database": config.bronze_db_path}


with DAG(
    dag_id="igh_ingestion",
    dag_display_name="1. IGH Ingestion",
    description="Sync data from Microsoft Dataverse to Bronze SQLite database",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["igh", "ingestion", "dataverse"],
) as dag:
    sync_task = PythonOperator(
        task_id="sync_dataverse",
        python_callable=sync_dataverse,
        execution_timeout=timedelta(hours=2),
    )
