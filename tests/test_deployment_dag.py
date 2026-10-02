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


def test_swap_sends_the_shared_swap_command(monkeypatch):
    """The DAG must delegate to swap_command, not hand-roll a command string."""
    import dags.igh_deployment_dag as dep
    from config.settings import config
    from dags.igh_deploy_remote import swap_command

    monkeypatch.setattr(config, "deploy_target_host", "dash.example.com")
    monkeypatch.setattr(config, "deploy_target_user", "deployer")
    monkeypatch.setattr(config, "deploy_target_path", "/srv/dashboard/data")

    sent = {}
    monkeypatch.setattr(dep, "run_remote", lambda command, **kw: sent.setdefault("command", command))

    result = dep.swap_remote_db()

    assert sent["command"] == swap_command("/srv/dashboard/data")
    assert result["status"] == "deployed"

    # The clause order is the safety property, so pin it at the DAG boundary
    # too: regenerating both sides of the equality above would not catch a
    # reordering. The executing test in test_deploy_remote.py is the stronger
    # guard; this one costs three lines on setup that already exists.
    guard = sent["command"].index("[ -f star_schema.db.new ]")
    aside = sent["command"].index("ln -f star_schema.db star_schema.db.prev")
    swap = sent["command"].index("mv -f star_schema.db.new star_schema.db")
    assert guard < aside < swap


def test_swap_skips_in_local_mode(monkeypatch):
    import dags.igh_deployment_dag as dep
    from config.settings import config

    monkeypatch.setattr(config, "deploy_target_host", "local")

    def explode(*args, **kwargs):
        raise AssertionError("run_remote must not be called in local mode")

    monkeypatch.setattr(dep, "run_remote", explode)

    assert dep.swap_remote_db() == {"status": "skipped", "reason": "local mode"}


def test_deployment_allows_only_one_active_run():
    """Concurrent deploys destroy the retained version.

    Two interleaved runs can both pass the `.new` guard; the second's `ln`
    then makes `.prev` and the live DB the same inode, after which rollback
    fails with a coreutils "are the same file" error instead of either
    designed message, and the operator cannot roll back until the next
    deploy resets `.prev`.
    """
    from dags.igh_deployment_dag import dag

    assert dag.max_active_runs == 1


def test_swap_uses_the_current_config_after_a_settings_reload(monkeypatch):
    """Reloading config.settings rebinds the singleton; the DAG must follow it.

    is_local_mode() and validate_deploy_config() live in the helper and read
    the fresh object. If this module kept a stale reference, those guards
    would validate one config while swap_command() was built from another --
    the boundary check would stop guarding the value actually used.
    """
    import importlib

    import config.settings
    import dags.igh_deployment_dag as dep

    importlib.reload(config.settings)
    fresh = config.settings.config
    monkeypatch.setattr(fresh, "deploy_target_host", "dash.example.com")
    monkeypatch.setattr(fresh, "deploy_target_user", "deployer")
    monkeypatch.setattr(fresh, "deploy_target_path", "/srv/after/reload")

    sent = {}
    monkeypatch.setattr(dep, "run_remote", lambda command, **kw: sent.setdefault("command", command))
    dep.swap_remote_db()

    assert "/srv/after/reload" in sent["command"]
