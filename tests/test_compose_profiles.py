"""Tests for the dev docker-compose service wiring.

These guard two things that are easy to break by accident and expensive to
notice: that the simulated dashboard server can never start as part of the
normal dev stack, and that the deploy settings still default to the local-mode
escape hatch rather than to a real SSH target.
"""

from pathlib import Path

import pytest
import yaml

COMPOSE_FILE = Path(__file__).parent.parent / "docker-compose.yml"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE_FILE.read_text())


def test_dashboard_sim_is_behind_a_profile(compose):
    """An sshd must never start as part of a plain `docker compose up -d`.

    Compose only starts a service with a non-empty `profiles` list when that
    profile is named explicitly, so this assertion is what keeps the simulated
    dashboard server opt-in.
    """
    sim = compose["services"]["dashboard-sim"]

    assert sim["profiles"], "dashboard-sim must declare a profile or it joins the default stack"
    assert "dashboard-sim" in sim["profiles"]


def test_deploy_settings_default_to_local_mode(compose):
    """Without explicit env, the deploy tasks must short-circuit, not reach out.

    `DEPLOY_TARGET_HOST` defaulting to `local` is what makes `is_local_mode()`
    true on a fresh checkout. If that default ever changes, a dev machine would
    start attempting real SCP and SSH.
    """
    env = compose["x-airflow-common"]["environment"]

    assert env["DEPLOY_TARGET_HOST"] == "${DEPLOY_TARGET_HOST:-local}"
    for var in ("DEPLOY_TARGET_USER", "DEPLOY_TARGET_PATH", "DEPLOY_SSH_KEY_PATH"):
        assert var in env, f"{var} is needed for the deploy DAGs to work in dev"


def test_airflow_containers_can_read_the_ssh_key(compose):
    """The deploy tasks authenticate with a key from ./ssh, so it must be mounted."""
    volumes = compose["x-airflow-common"]["volumes"]

    assert any("/opt/airflow/ssh" in v for v in volumes), f"no ssh mount in {volumes}"
