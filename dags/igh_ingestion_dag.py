"""IGH Ingestion DAG - Syncs data from Microsoft Dataverse to Bronze database."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import Param

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import config, get_env

default_args = {
    "owner": "igh",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

logger = logging.getLogger(__name__)


def sync_dataverse(**context):
    """Sync data from Microsoft Dataverse to Bronze SQLite database using igh-data-sync.

    Param `update_mode` (bool, default False):
        - False: delete the existing bronze DB before sync (fresh build).
        - True:  keep the existing bronze DB and sync incrementally.
    """
    from igh_data_sync import run_sync
    from igh_data_sync.config import Config

    update_mode = bool(context["params"]["update_mode"])
    logger.info("Starting Dataverse sync (update_mode=%s)...", update_mode)

    # Ensure bronze directory exists
    bronze_path = Path(config.bronze_db_path)
    bronze_path.parent.mkdir(parents=True, exist_ok=True)

    # Fresh-build cleanup: when update_mode is False, remove any existing
    # bronze DB so this run rebuilds from scratch. This matches the default
    # behavior of sync-and-run-etl.sh. Cleanup stays inline (rather than a
    # separate task) so a retry re-runs delete-then-sync atomically.
    if not update_mode:
        if bronze_path.exists():
            logger.info(
                "update_mode=False; deleting existing bronze DB at %s before fresh sync",
                bronze_path,
            )
            bronze_path.unlink()
        else:
            logger.info(
                "update_mode=False; no existing bronze DB at %s; proceeding with fresh sync",
                bronze_path,
            )
    else:
        logger.info(
            "update_mode=True; keeping existing bronze DB at %s",
            bronze_path,
        )

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
    params={
        "update_mode": Param(
            False,
            type="boolean",
            title="Update mode (incremental sync)",
            description=(
                "When false (default), the existing bronze database is "
                "deleted before sync to produce a fresh build, matching "
                "sync-and-run-etl.sh. When true, the existing bronze "
                "database is kept and sync runs incrementally."
            ),
        ),
    },
) as dag:
    sync_task = PythonOperator(
        task_id="sync_dataverse",
        python_callable=sync_dataverse,
        execution_timeout=timedelta(hours=2),
    )
