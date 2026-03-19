"""IGH Transform DAG - Transforms data from Bronze to Silver and Gold layers."""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import config
from utils.slack_alerts import send_failure_alert, send_success_alert

default_args = {
    "owner": "igh",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": send_failure_alert,
}

logger = logging.getLogger(__name__)


def run_bronze_to_silver(**context):
    """Transform Bronze layer to Silver layer using igh-data-transform."""
    from igh_data_transform import bronze_to_silver

    bronze_path = Path(config.bronze_db_path)
    silver_path = Path(config.silver_db_path)

    # Ensure output directory exists
    silver_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Starting Bronze to Silver transformation")
    logger.info("Source: %s", bronze_path)
    logger.info("Target: %s", silver_path)

    success = bronze_to_silver(
        bronze_db_path=str(bronze_path),
        silver_db_path=str(silver_path),
    )

    if not success:
        raise RuntimeError("Bronze to Silver transformation failed")

    logger.info("Bronze to Silver transformation completed successfully")
    return {"status": "success", "source": str(bronze_path), "target": str(silver_path)}


def run_silver_to_gold(**context):
    """Transform Silver layer to Gold layer using igh-data-transform."""
    from igh_data_transform import silver_to_gold

    silver_path = Path(config.silver_db_path)

    logger.info("Starting Silver to Gold transformation")
    logger.info("Source: %s", silver_path)

    # Note: silver_to_gold is currently a stub in igh-data-transform
    success = silver_to_gold(silver_db_path=str(silver_path))

    if not success:
        raise RuntimeError("Silver to Gold transformation failed")

    logger.info("Silver to Gold transformation completed successfully")
    return {"status": "success", "source": str(silver_path)}


with DAG(
    dag_id="igh_transform",
    dag_display_name="2. IGH Transform",
    description="Transform data from Bronze to Silver and Gold layers",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["igh", "transform", "silver", "gold"],
    on_success_callback=send_success_alert,
) as dag:
    bronze_to_silver_task = PythonOperator(
        task_id="bronze_to_silver",
        python_callable=run_bronze_to_silver,
        execution_timeout=timedelta(hours=1),
    )

    silver_to_gold_task = PythonOperator(
        task_id="silver_to_gold",
        python_callable=run_silver_to_gold,
        execution_timeout=timedelta(hours=1),
    )

    bronze_to_silver_task >> silver_to_gold_task
