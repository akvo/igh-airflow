"""Tests for the IGH Rollback DAG."""

import pytest


@pytest.fixture(autouse=True)
def _reset_rollback_dag_module():
    """Reload config and DAG modules after each test.

    test_rollback_dag_is_manual_only reloads both modules with
    DEPLOY_AUTO_TRIGGER set; monkeypatch restores the env var but does not
    re-reload, so sys.modules would otherwise keep the patched module.
    """
    yield
    import importlib
    import os

    import config.settings
    import dags.igh_rollback_dag

    os.environ.pop("DEPLOY_AUTO_TRIGGER", None)
    importlib.reload(config.settings)
    importlib.reload(dags.igh_rollback_dag)


def test_dag_loads():
    from dags.igh_rollback_dag import dag

    assert dag is not None
    assert dag.dag_id == "igh_rollback"


def test_dag_has_correct_tags():
    from dags.igh_rollback_dag import dag

    assert "igh" in dag.tags
    assert "rollback" in dag.tags


def test_dag_has_one_task():
    from dags.igh_rollback_dag import dag

    assert [task.task_id for task in dag.tasks] == ["rollback_remote_db"]


def test_rollback_dag_is_manual_only(monkeypatch):
    """Review Focus 5: a gold build must never be able to trigger a rollback.

    This DAG is written by following igh_deployment_dag's patterns, and that
    DAG is Asset-scheduled when DEPLOY_AUTO_TRIGGER is set. Inheriting that
    line here would auto-roll-back on every successful transform.
    """
    monkeypatch.setenv("DEPLOY_AUTO_TRIGGER", "true")
    import importlib

    import config.settings
    import dags.igh_rollback_dag as rb

    importlib.reload(config.settings)
    importlib.reload(rb)

    assert rb.dag.schedule is None


def test_rollback_does_not_retry():
    """Rollback is a deliberate act during an incident, not a retryable job."""
    from dags.igh_rollback_dag import dag

    assert dag.get_task("rollback_remote_db").retries == 0


def test_rollback_sends_the_shared_rollback_command(monkeypatch):
    import dags.igh_rollback_dag as rb
    from config.settings import config
    from dags.igh_deploy_remote import rollback_command

    monkeypatch.setattr(config, "deploy_target_host", "dash.example.com")
    monkeypatch.setattr(config, "deploy_target_user", "deployer")
    monkeypatch.setattr(config, "deploy_target_path", "/srv/dashboard/data")

    sent = {}
    monkeypatch.setattr(rb, "run_remote", lambda command, **kw: sent.setdefault("command", command))

    result = rb.rollback_remote_db()

    assert sent["command"] == rollback_command("/srv/dashboard/data")
    assert result["status"] == "rolled_back"


def test_rollback_skips_in_local_mode(monkeypatch):
    import dags.igh_rollback_dag as rb
    from config.settings import config

    monkeypatch.setattr(config, "deploy_target_host", "local")

    def explode(*args, **kwargs):
        raise AssertionError("run_remote must not be called in local mode")

    monkeypatch.setattr(rb, "run_remote", explode)

    assert rb.rollback_remote_db() == {"status": "skipped", "reason": "local mode"}


def test_rollback_validates_deploy_config(monkeypatch):
    import dags.igh_rollback_dag as rb
    from config.settings import config

    monkeypatch.setattr(config, "deploy_target_host", "dash.example.com")
    monkeypatch.setattr(config, "deploy_target_user", "")
    monkeypatch.setattr(config, "deploy_target_path", "")
    monkeypatch.setattr(rb, "run_remote", lambda *a, **kw: None)

    with pytest.raises(ValueError, match="DEPLOY_TARGET_USER"):
        rb.rollback_remote_db()
