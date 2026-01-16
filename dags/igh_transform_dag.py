"""IGH Transform DAG - Transforms data from Bronze to Silver and Gold layers."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.external_task import ExternalTaskSensor

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


with DAG(
    dag_id="igh_transform",
    description="Transform data from Bronze to Silver and Gold layers",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=config.transform_schedule,
    catchup=False,
    tags=["igh", "transform", "silver", "gold"],
    on_success_callback=send_success_alert,
) as dag:
    # Wait for ingestion DAG to complete
    wait_for_ingestion = ExternalTaskSensor(
        task_id="wait_for_ingestion",
        external_dag_id="igh_ingestion",
        external_task_id=None,  # Wait for entire DAG
        mode="reschedule",
        timeout=3600,
        poke_interval=60,
    )

    # Transform Bronze to Silver
    # TODO: Replace with actual igh-transform CLI when available
    bronze_to_silver = BashOperator(
        task_id="bronze_to_silver",
        bash_command=f"""
            echo "Transforming Bronze to Silver..."
            echo "Bronze DB: {config.bronze_db_path}"
            echo "Silver DB: {config.silver_db_path}"
            mkdir -p $(dirname {config.silver_db_path})
            # igh-transform bronze-to-silver --source {config.bronze_db_path} --target {config.silver_db_path}
            echo "Bronze to Silver transformation complete"
        """,
        execution_timeout=timedelta(hours=1),
    )

    # Transform Silver to Gold
    # TODO: Replace with actual igh-transform CLI when available
    silver_to_gold = BashOperator(
        task_id="silver_to_gold",
        bash_command=f"""
            echo "Transforming Silver to Gold..."
            echo "Silver DB: {config.silver_db_path}"
            # igh-transform silver-to-gold --source {config.silver_db_path}
            echo "Silver to Gold transformation complete"
        """,
        execution_timeout=timedelta(hours=1),
    )

    wait_for_ingestion >> bronze_to_silver >> silver_to_gold
