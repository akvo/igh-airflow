"""IGH Deployment DAG - Deploys validated data to production."""

import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
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


def verify_silver_database(**context):
    """Verify Silver database integrity before deployment."""
    import logging
    import sqlite3

    logger = logging.getLogger(__name__)
    silver_path = Path(config.silver_db_path)

    logger.info(f"Verifying Silver database at {silver_path}")

    if not silver_path.exists():
        raise FileNotFoundError(f"Silver database not found: {silver_path}")

    # Basic integrity check
    conn = sqlite3.connect(silver_path)
    try:
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        if result != "ok":
            raise ValueError(f"Database integrity check failed: {result}")
        logger.info("Silver database integrity verified")
    finally:
        conn.close()

    return {"status": "verified", "path": str(silver_path)}


def deploy_to_production(**context):
    """Deploy Silver database to production with atomic swap."""
    import logging

    logger = logging.getLogger(__name__)

    silver_path = Path(config.silver_db_path)
    production_path = Path(config.production_db_path)
    backup_path = production_path.with_suffix(".db.backup")

    logger.info(f"Deploying {silver_path} to {production_path}")

    # Ensure production directory exists
    production_path.parent.mkdir(parents=True, exist_ok=True)

    # Backup existing production database
    if production_path.exists():
        logger.info(f"Backing up existing production database to {backup_path}")
        shutil.copy2(production_path, backup_path)

    try:
        # Atomic copy to production
        temp_path = production_path.with_suffix(".db.tmp")
        shutil.copy2(silver_path, temp_path)
        temp_path.rename(production_path)
        logger.info("Production deployment successful")

        # Remove backup on success
        if backup_path.exists():
            backup_path.unlink()

    except Exception as e:
        # Rollback on failure
        logger.error(f"Deployment failed: {e}")
        if backup_path.exists():
            logger.info("Rolling back to backup")
            shutil.copy2(backup_path, production_path)
        raise

    return {"status": "deployed", "path": str(production_path)}


def verify_production_database(**context):
    """Verify production database after deployment."""
    import logging
    import sqlite3

    logger = logging.getLogger(__name__)
    production_path = Path(config.production_db_path)

    logger.info(f"Verifying production database at {production_path}")

    if not production_path.exists():
        raise FileNotFoundError(f"Production database not found: {production_path}")

    # Basic integrity check
    conn = sqlite3.connect(production_path)
    try:
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        if result != "ok":
            raise ValueError(f"Database integrity check failed: {result}")
        logger.info("Production database integrity verified")
    finally:
        conn.close()

    return {"status": "verified", "path": str(production_path)}


with DAG(
    dag_id="igh_deployment",
    description="Deploy validated data to production database",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=config.deployment_schedule,
    catchup=False,
    tags=["igh", "deployment", "production"],
    on_success_callback=send_success_alert,
) as dag:
    # Wait for transform DAG to complete
    wait_for_transform = ExternalTaskSensor(
        task_id="wait_for_transform",
        external_dag_id="igh_transform",
        external_task_id=None,  # Wait for entire DAG
        mode="reschedule",
        timeout=3600,
        poke_interval=60,
    )

    verify_source = PythonOperator(
        task_id="verify_silver_database",
        python_callable=verify_silver_database,
    )

    deploy = PythonOperator(
        task_id="deploy_to_production",
        python_callable=deploy_to_production,
    )

    verify_target = PythonOperator(
        task_id="verify_production_database",
        python_callable=verify_production_database,
    )

    wait_for_transform >> verify_source >> deploy >> verify_target
