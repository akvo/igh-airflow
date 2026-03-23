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
