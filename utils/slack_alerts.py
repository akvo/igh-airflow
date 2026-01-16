"""Slack alerting utilities for Airflow DAGs."""

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


def get_slack_webhook_url() -> str | None:
    """Get Slack webhook URL from environment or Airflow Variable."""
    url = os.getenv("SLACK_WEBHOOK_URL")
    if url:
        return url

    try:
        from airflow.models import Variable

        return Variable.get("slack_webhook_url", default_var=None)
    except Exception:
        return None


def send_slack_message(message: str, webhook_url: str | None = None) -> bool:
    """Send a message to Slack webhook."""
    url = webhook_url or get_slack_webhook_url()
    if not url:
        logger.warning("Slack webhook URL not configured, skipping notification")
        return False

    try:
        response = requests.post(url, json={"text": message}, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send Slack message: {e}")
        return False


def send_failure_alert(context: dict[str, Any]) -> None:
    """Send Slack alert on task failure. Use as on_failure_callback."""
    dag_id = context.get("dag").dag_id if context.get("dag") else "unknown"
    task_id = context.get("task_instance").task_id if context.get("task_instance") else "unknown"
    execution_date = context.get("execution_date", "unknown")
    exception = context.get("exception", "No exception details")

    message = (
        f":red_circle: *Task Failed*\n"
        f"*DAG:* {dag_id}\n"
        f"*Task:* {task_id}\n"
        f"*Execution Date:* {execution_date}\n"
        f"*Error:* {exception}"
    )
    send_slack_message(message)


def send_success_alert(context: dict[str, Any]) -> None:
    """Send Slack alert on DAG success. Use as on_success_callback."""
    dag_id = context.get("dag").dag_id if context.get("dag") else "unknown"
    execution_date = context.get("execution_date", "unknown")

    message = (
        f":large_green_circle: *DAG Completed Successfully*\n"
        f"*DAG:* {dag_id}\n"
        f"*Execution Date:* {execution_date}"
    )
    send_slack_message(message)
