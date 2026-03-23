"""IGH Deployment DAG - Deploys validated data to production."""

import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import config

default_args = {
    "owner": "igh",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


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


with DAG(
    dag_id="igh_deployment",
    dag_display_name="3. IGH Deployment",
    description="Deploy validated data to production database",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["igh", "deployment", "production"],
) as dag:
    deploy = PythonOperator(
        task_id="deploy_to_production",
        python_callable=deploy_to_production,
    )
