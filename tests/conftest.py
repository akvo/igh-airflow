"""Pytest fixtures for IGH Airflow tests."""

import sys
from pathlib import Path

import pytest

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "dags"))


@pytest.fixture(autouse=True)
def mock_airflow_env(monkeypatch):
    """Set up minimal Airflow environment for testing."""
    monkeypatch.setenv("AIRFLOW_HOME", "/tmp/airflow")
    monkeypatch.setenv("AIRFLOW__CORE__UNIT_TEST_MODE", "True")


@pytest.fixture
def mock_context():
    """Create a mock Airflow task context."""
    from unittest.mock import MagicMock

    dag = MagicMock()
    dag.dag_id = "test_dag"

    task_instance = MagicMock()
    task_instance.task_id = "test_task"

    return {
        "dag": dag,
        "task_instance": task_instance,
        "execution_date": "2024-01-01T00:00:00",
        "exception": Exception("Test error"),
    }
