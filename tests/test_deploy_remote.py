"""Tests for the remote-publish protocol shared by deployment and rollback.

The command builders return shell strings that normally run on the dashboard
server over SSH. Here they are run locally with ``bash`` against a temporary
directory, which exercises the real logic -- the clause ordering, the
preconditions, and the atomic rename -- without needing a remote host.
"""

import subprocess
from pathlib import Path

import pytest

from dags.igh_deploy_remote import (
    NOTHING_TO_ROLL_BACK,
    RemoteCommandError,
    is_local_mode,
    rollback_command,
    run_remote,
    swap_command,
    validate_deploy_config,
)


def _run(command):
    """Execute a generated command string, returning (returncode, stderr)."""
    result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)
    return result.returncode, result.stderr.strip()


def _state(directory):
    """Every file in the directory as {name: contents}, for asserting on state."""
    return {p.name: p.read_text() for p in sorted(Path(directory).iterdir())}


# --- deploy swap -------------------------------------------------------------


def test_swap_first_ever_deploy_creates_no_prev(tmp_path):
    """The first deploy has no live DB to set aside, and must not invent a .prev."""
    (tmp_path / "star_schema.db.new").write_text("v1")

    rc, _ = _run(swap_command(tmp_path))

    assert rc == 0
    assert _state(tmp_path) == {"star_schema.db": "v1"}


def test_swap_keeps_one_previous_version(tmp_path):
    (tmp_path / "star_schema.db").write_text("v1")
    (tmp_path / "star_schema.db.new").write_text("v2")

    rc, _ = _run(swap_command(tmp_path))

    assert rc == 0
    assert _state(tmp_path) == {"star_schema.db": "v2", "star_schema.db.prev": "v1"}


def test_swap_retains_only_the_most_recent_previous_version(tmp_path):
    """A third deploy replaces .prev rather than accumulating history."""
    (tmp_path / "star_schema.db.prev").write_text("v1")
    (tmp_path / "star_schema.db").write_text("v2")
    (tmp_path / "star_schema.db.new").write_text("v3")

    rc, _ = _run(swap_command(tmp_path))

    assert rc == 0
    assert _state(tmp_path) == {"star_schema.db": "v3", "star_schema.db.prev": "v2"}


def test_swap_without_new_leaves_live_db_untouched(tmp_path):
    """Review Focus 1: the guard must run before anything is mutated.

    Any successful deploy consumes .new, so rerunning this task from the
    Airflow UI reaches this state. Setting the live DB aside first and only
    then discovering .new is missing would leave no live database at all.
    """
    (tmp_path / "star_schema.db").write_text("v1")
    before = _state(tmp_path)

    rc, stderr = _run(swap_command(tmp_path))

    assert rc != 0
    assert "no star_schema.db.new" in stderr
    assert _state(tmp_path) == before


def test_swap_reports_whether_it_retained_a_previous_version(tmp_path):
    """The DAG logs "rollback is available" off this, so it must be truthful.

    On a first deploy there is nothing to set aside, and claiming otherwise
    tells an operator a rollback exists when it does not.
    """

    def stdout_of(command):
        return subprocess.run(["bash", "-c", command], capture_output=True, text=True, check=True).stdout

    (tmp_path / "star_schema.db.new").write_text("v1")
    assert "retained-prev" not in stdout_of(swap_command(tmp_path))

    (tmp_path / "star_schema.db.new").write_text("v2")
    assert "retained-prev" in stdout_of(swap_command(tmp_path))


def test_swap_hardlinks_rather_than_copying(tmp_path):
    """.prev must be the same inode as the outgoing live DB, so nothing is copied.

    This pins only that: runtime stays independent of database size. It does
    *not* prove the live path was never unlinked -- an `mv`-based aside would
    also preserve the inode and pass. The clause ordering is what guarantees
    that, and `test_swap_without_new_leaves_live_db_untouched` is what proves
    the consequence that matters.
    """
    live = tmp_path / "star_schema.db"
    live.write_text("v1")
    outgoing_inode = live.stat().st_ino
    (tmp_path / "star_schema.db.new").write_text("v2")

    rc, _ = _run(swap_command(tmp_path))

    assert rc == 0
    assert (tmp_path / "star_schema.db.prev").stat().st_ino == outgoing_inode


# --- rollback ----------------------------------------------------------------


def test_rollback_restores_previous_and_consumes_prev(tmp_path):
    (tmp_path / "star_schema.db").write_text("v2")
    (tmp_path / "star_schema.db.prev").write_text("v1")

    rc, _ = _run(rollback_command(tmp_path))

    assert rc == 0
    assert _state(tmp_path) == {"star_schema.db": "v1"}


def test_rollback_without_prev_exits_with_the_nothing_to_roll_back_code(tmp_path):
    """Review Focus 2: back-to-back rollbacks are impossible by construction.

    The exit code is load-bearing, not incidental: the DAG turns this specific
    code into a skipped task rather than a red one, and treats every other
    non-zero exit as a real failure. Exit 3 is unused by `mv` (1), `test`
    (1 false / 2 error) and the shell itself (127, 128+n), so it cannot
    collide with a genuine error.
    """
    (tmp_path / "star_schema.db").write_text("v1")
    before = _state(tmp_path)

    rc, stderr = _run(rollback_command(tmp_path))

    assert rc == NOTHING_TO_ROLL_BACK
    assert "no star_schema.db.prev" in stderr
    assert _state(tmp_path) == before


def test_swap_without_new_keeps_a_generic_failure_code(tmp_path):
    """A missing .new stays a plain failure, deliberately unlike rollback.

    Rollback having nothing to undo is an expected state. An upload that did
    not land where it should have is anomalous and must stay red, so this
    guard must not be "harmonized" onto the rollback's skip code.
    """
    (tmp_path / "star_schema.db").write_text("v1")

    rc, _ = _run(swap_command(tmp_path))

    assert rc == 1
    assert rc != NOTHING_TO_ROLL_BACK


def test_rolling_forward_after_a_rollback_re_establishes_prev(tmp_path):
    """The one sequencing claim the single-step tests above do not cover.

    After a rollback there is no `.prev`, so the next deploy has to create one
    again -- otherwise rollback would be available only once per lifetime.
    """
    (tmp_path / "star_schema.db").write_text("v1")
    (tmp_path / "star_schema.db.new").write_text("v2")
    _run(swap_command(tmp_path))
    _run(rollback_command(tmp_path))

    (tmp_path / "star_schema.db.new").write_text("v3")

    assert _run(swap_command(tmp_path))[0] == 0
    assert _state(tmp_path) == {"star_schema.db": "v3", "star_schema.db.prev": "v1"}


def test_commands_quote_paths_containing_spaces(tmp_path):
    """DEPLOY_TARGET_PATH is operator-supplied; an unquoted path would split."""
    spaced = tmp_path / "deploy dir"
    spaced.mkdir()
    (spaced / "star_schema.db.new").write_text("v1")

    rc, _ = _run(swap_command(spaced))

    assert rc == 0
    assert _state(spaced) == {"star_schema.db": "v1"}


# --- SSH execution and config ------------------------------------------------


def test_run_remote_builds_ssh_command(monkeypatch):
    from config.settings import config

    monkeypatch.setattr(config, "deploy_target_host", "dash.example.com")
    monkeypatch.setattr(config, "deploy_target_user", "deployer")
    monkeypatch.setattr(config, "deploy_ssh_key_path", "/opt/airflow/ssh/id_rsa")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("dags.igh_deploy_remote.subprocess.run", fake_run)

    run_remote("echo hello", timeout=42)

    assert captured["cmd"] == [
        "ssh",
        "-i",
        "/opt/airflow/ssh/id_rsa",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "deployer@dash.example.com",
        "echo hello",
    ]
    assert captured["kwargs"]["timeout"] == 42


def test_run_remote_raises_with_remote_stderr(monkeypatch):
    """Review Focus 4: the precondition's own message must reach the task log."""

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no star_schema.db.prev to roll back to\n")

    monkeypatch.setattr("dags.igh_deploy_remote.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="no star_schema.db.prev to roll back to"):
        run_remote("false")


def test_run_remote_error_carries_the_exit_code(monkeypatch):
    """Callers branch on the exit code, so it must survive the raise."""

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, NOTHING_TO_ROLL_BACK, stdout="", stderr="nothing to do\n")

    monkeypatch.setattr("dags.igh_deploy_remote.subprocess.run", fake_run)

    with pytest.raises(RemoteCommandError) as exc:
        run_remote("false")

    assert exc.value.returncode == NOTHING_TO_ROLL_BACK
    assert "nothing to do" in str(exc.value)


def test_is_local_mode_for_dev_hosts(monkeypatch):
    from config.settings import config

    for host, expected in (("local", True), ("", True), ("dash.example.com", False)):
        monkeypatch.setattr(config, "deploy_target_host", host)
        assert is_local_mode() is expected


def test_validate_deploy_config_names_every_missing_setting(monkeypatch):
    from config.settings import config

    monkeypatch.setattr(config, "deploy_target_user", "")
    monkeypatch.setattr(config, "deploy_target_path", "")

    with pytest.raises(ValueError) as exc:
        validate_deploy_config()

    assert "DEPLOY_TARGET_USER" in str(exc.value)
    assert "DEPLOY_TARGET_PATH" in str(exc.value)
