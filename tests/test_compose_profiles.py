"""Tests for the dev docker-compose service wiring."""

from pathlib import Path

import yaml

COMPOSE_FILE = Path(__file__).parent.parent / "docker-compose.yml"


def test_dashboard_sim_is_behind_a_profile():
    """An sshd must never start as part of a plain `docker compose up -d`.

    Compose only starts a service with a non-empty `profiles` list when that
    profile is named explicitly, so this assertion is what keeps the simulated
    dashboard server opt-in. Everything else about the service fails loudly the
    first time someone runs the profile, so it needs no test.
    """
    compose = yaml.safe_load(COMPOSE_FILE.read_text())
    sim = compose["services"]["dashboard-sim"]

    assert sim["profiles"], "dashboard-sim must declare a profile or it joins the default stack"
    assert "dashboard-sim" in sim["profiles"]
