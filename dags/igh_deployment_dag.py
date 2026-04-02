"""IGH Deployment DAG - Deploys gold database to remote dashboard server."""

import subprocess
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


def _is_local_mode():
    return config.deploy_target_host in ("local", "")


def _validate_deploy_config():
    """Raise if required deploy settings are missing."""
    missing = []
    if not config.deploy_target_user:
        missing.append("DEPLOY_TARGET_USER")
    if not config.deploy_target_path:
        missing.append("DEPLOY_TARGET_PATH")
    if missing:
        raise ValueError(f"Missing required deploy config: {', '.join(missing)}")


def scp_gold_db(**context):
    """SCP the gold star-schema database to the remote server."""
    import logging

    logger = logging.getLogger(__name__)

    if _is_local_mode():
        logger.warning("Skipping SCP — DEPLOY_TARGET_HOST is 'local' (dev mode)")
        return {"status": "skipped", "reason": "local mode"}

    _validate_deploy_config()

    gold_path = Path(config.gold_db_path)
    if not gold_path.exists():
        raise FileNotFoundError(f"Gold database not found: {gold_path}")

    target = (
        f"{config.deploy_target_user}@{config.deploy_target_host}"
        f":{config.deploy_target_path}/star_schema.db.new"
    )
    cmd = [
        "scp",
        "-i", config.deploy_ssh_key_path,
        "-o", "StrictHostKeyChecking=accept-new",
        str(gold_path),
        target,
    ]

    logger.info(f"SCP gold DB to {target}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"SCP failed (rc={result.returncode}): {result.stderr}")

    logger.info("SCP completed successfully")
    return {"status": "uploaded", "target": target}


def swap_remote_db(**context):
    """Atomically swap star_schema.db.new to star_schema.db on the remote server."""
    import logging

    logger = logging.getLogger(__name__)

    if _is_local_mode():
        logger.warning("Skipping swap — DEPLOY_TARGET_HOST is 'local' (dev mode)")
        return {"status": "skipped", "reason": "local mode"}

    _validate_deploy_config()

    # mv on the same filesystem is atomic and changes the inode, which
    # triggers the dashboard backend's hot-reload (DatabaseManager detects
    # inode changes and reconnects automatically).
    swap_cmd = (
        f"mv {config.deploy_target_path}/star_schema.db.new"
        f" {config.deploy_target_path}/star_schema.db"
    )
    cmd = [
        "ssh",
        "-i", config.deploy_ssh_key_path,
        "-o", "StrictHostKeyChecking=accept-new",
        f"{config.deploy_target_user}@{config.deploy_target_host}",
        swap_cmd,
    ]

    logger.info(f"Swapping DB on {config.deploy_target_host}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"SSH swap failed (rc={result.returncode}): {result.stderr}")

    logger.info("Remote DB swap completed successfully")
    return {"status": "deployed", "host": config.deploy_target_host}


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
    scp_task = PythonOperator(
        task_id="scp_gold_db",
        python_callable=scp_gold_db,
    )

    swap_task = PythonOperator(
        task_id="swap_remote_db",
        python_callable=swap_remote_db,
    )

    scp_task >> swap_task
