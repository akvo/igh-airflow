"""IGH Rollback DAG - Restores the previous gold database on the dashboard server.

Manual-trigger only, and deliberately never Asset-scheduled: this DAG undoes
a deployment, so nothing upstream should be able to fire it.

It restores ``star_schema.db.prev``, which ``igh_deployment``'s swap task
leaves behind. That consumes ``.prev``, so only one step back is available --
a second rollback fails with a clear message and changes nothing. To roll
forward again, trigger ``igh_deployment``, which re-uploads from the local
gold database.
"""

import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from igh_deploy_remote import is_local_mode, rollback_command, run_remote, validate_deploy_config

# Read settings through the module, never by holding the ``config`` object:
# reloading ``config.settings`` rebinds the singleton, and the guards in
# igh_deploy_remote read the fresh one. A stale reference here would let the
# boundary check validate a different config than the command is built from.
from config import settings

default_args = {
    "owner": "igh",
    "depends_on_past": False,
    # No retries: rollback is a deliberate act during an incident, and every
    # way it can fail happens before the directory is modified, so a silent
    # second attempt would add noise without adding safety.
    "retries": 0,
}


def rollback_remote_db(**context):
    """Restore star_schema.db.prev as the live database on the dashboard server."""
    import logging

    logger = logging.getLogger(__name__)

    if is_local_mode():
        logger.warning("Skipping rollback — DEPLOY_TARGET_HOST is 'local' (dev mode)")
        return {"status": "skipped", "reason": "local mode"}

    validate_deploy_config()

    logger.info(f"Rolling back DB on {settings.config.deploy_target_host}")
    run_remote(rollback_command(settings.config.deploy_target_path), timeout=60)

    logger.info("Rollback completed; star_schema.db.prev is now live and has been consumed")
    return {"status": "rolled_back", "host": settings.config.deploy_target_host}


with DAG(
    dag_id="igh_rollback",
    dag_display_name="4. IGH Rollback",
    description="Restore the previous gold database on the dashboard server",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    # One rollback at a time. Two concurrent runs can both pass the .prev
    # check; the loser then dies on a coreutils message instead of the
    # designed one, which is the last thing an operator needs mid-incident.
    max_active_runs=1,
    catchup=False,
    tags=["igh", "rollback", "production"],
) as dag:
    PythonOperator(
        task_id="rollback_remote_db",
        python_callable=rollback_remote_db,
    )
