"""Tests for IGH Deployment DAG."""

import importlib
import os

import pytest


@pytest.fixture(autouse=True)
def _reset_deployment_dag_module():
    """Reload config and DAG modules after each test.

    Tests that monkeypatch DEPLOY_AUTO_TRIGGER reload both modules to pick up
    the env change; monkeypatch restores the env var on teardown but does NOT
    re-reload, so sys.modules is left with the patched DAG. This fixture
    ensures the module is always reset to the default (no-flag) state,
    preventing schedule state from leaking into later tests.
    """
    yield
    import config.settings
    import dags.igh_deployment_dag

    os.environ.pop("DEPLOY_AUTO_TRIGGER", None)
    importlib.reload(config.settings)
    importlib.reload(dags.igh_deployment_dag)


def test_dag_loads():
    """Test that the deployment DAG loads without errors."""
    from dags.igh_deployment_dag import dag

    assert dag is not None
    assert dag.dag_id == "igh_deployment"


def test_dag_has_correct_tags():
    """Test that the DAG has the expected tags."""
    from dags.igh_deployment_dag import dag

    assert "igh" in dag.tags
    assert "deployment" in dag.tags


def test_dag_manual_by_default(monkeypatch):
    """Without the flag, deployment stays manual-trigger only."""
    monkeypatch.delenv("DEPLOY_AUTO_TRIGGER", raising=False)
    import importlib

    import config.settings
    import dags.igh_deployment_dag as dep

    importlib.reload(config.settings)
    importlib.reload(dep)
    assert dep.dag.schedule is None


def test_dag_auto_triggered_when_enabled(monkeypatch):
    """With DEPLOY_AUTO_TRIGGER=true, deployment is scheduled on gold."""
    monkeypatch.setenv("DEPLOY_AUTO_TRIGGER", "true")
    import importlib

    import config.settings
    import dags.igh_deployment_dag as dep

    importlib.reload(config.settings)
    importlib.reload(dep)
    assert [a.name for a in dep.dag.schedule] == ["igh_gold_db"]


def test_dag_has_tasks():
    """Test that the DAG has the expected tasks."""
    from dags.igh_deployment_dag import dag

    task_ids = [task.task_id for task in dag.tasks]
    assert "scp_gold_db" in task_ids
    assert "swap_remote_db" in task_ids


def test_dag_task_count():
    """Test that the DAG has the expected number of tasks."""
    from dags.igh_deployment_dag import dag

    assert len(dag.tasks) == 2


def test_task_ordering():
    """Test that scp_gold_db runs before swap_remote_db."""
    from dags.igh_deployment_dag import dag

    scp_task = dag.get_task("scp_gold_db")
    downstream_ids = [t.task_id for t in scp_task.downstream_list]
    assert "swap_remote_db" in downstream_ids
