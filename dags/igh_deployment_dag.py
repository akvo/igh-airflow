"""IGH Deployment DAG - Deploys gold database to remote dashboard server."""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from igh_assets import gold_asset
from igh_deploy_remote import is_local_mode, run_remote, swap_command, validate_deploy_config

# Read settings through the module, never by holding the ``config`` object:
# reloading ``config.settings`` rebinds the singleton, and the guards in
# igh_deploy_remote read the fresh one. A stale reference here would let the
# boundary check validate a different config than the command is built from.
from config import settings

default_args = {
    "owner": "igh",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def scp_gold_db(**context):
    """SCP the gold star-schema database to the remote server."""
    import logging

    logger = logging.getLogger(__name__)

    if is_local_mode():
        logger.warning("Skipping SCP — DEPLOY_TARGET_HOST is 'local' (dev mode)")
        return {"status": "skipped", "reason": "local mode"}

    validate_deploy_config()

    gold_path = Path(settings.config.gold_db_path)
    if not gold_path.exists():
        raise FileNotFoundError(f"Gold database not found: {gold_path}")

    target = f"{settings.config.deploy_target_user}@{settings.config.deploy_target_host}:{settings.config.deploy_target_path}/star_schema.db.new"
    cmd = [
        "scp",
        "-i",
        settings.config.deploy_ssh_key_path,
        "-o",
        "StrictHostKeyChecking=accept-new",
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
    """Publish the uploaded gold DB, keeping the previous version as .prev."""
    import logging

    logger = logging.getLogger(__name__)

    if is_local_mode():
        logger.warning("Skipping swap — DEPLOY_TARGET_HOST is 'local' (dev mode)")
        return {"status": "skipped", "reason": "local mode"}

    validate_deploy_config()

    logger.info(f"Swapping DB on {settings.config.deploy_target_host}")
    run_remote(swap_command(settings.config.deploy_target_path), timeout=60)

    logger.info("Remote DB swap completed successfully; previous version kept as star_schema.db.prev")
    return {"status": "deployed", "host": settings.config.deploy_target_host}


with DAG(
    dag_id="igh_deployment",
    dag_display_name="3. IGH Deployment",
    description="Deploy validated data to production database",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=[gold_asset] if settings.config.deploy_auto_trigger else None,
    # One deploy at a time. Two interleaved runs can both pass the .new guard;
    # the second's `ln` then points .prev at the same inode as the live DB, and
    # rollback afterwards fails with "are the same file" instead of either
    # designed message -- the operator cannot roll back until the next deploy.
    max_active_runs=1,
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
