"""Shared remote-publish protocol for the gold database.

Both ``igh_deployment`` and ``igh_rollback`` move files around in the same
directory on the dashboard server over SSH, so the connection handling, the
config validation, and the two command strings live here instead of being
duplicated in each DAG.

The deploy directory holds three filenames, each with exactly one meaning:

- ``star_schema.db``      -- live, what the dashboard serves
- ``star_schema.db.prev`` -- the one previous live version
- ``star_schema.db.new``  -- uploaded by scp, awaiting swap

Both commands have the same shape: check the precondition, establish the
aside link, then perform exactly one atomic rename. That ordering is a
safety property, not a style choice -- see the notes on each builder.
"""

import logging
import shlex
import subprocess
import sys
from pathlib import Path

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module, not the ``config`` object: the test suite reloads
# ``config.settings`` (to re-read DEPLOY_AUTO_TRIGGER at DAG-parse time), which
# rebinds the singleton. A module holding a direct reference would keep reading
# the pre-reload object forever.
from config import settings

logger = logging.getLogger(__name__)


def is_local_mode():
    """True when there is no real dashboard server to publish to (dev mode)."""
    return settings.config.deploy_target_host in ("local", "")


def validate_deploy_config():
    """Raise if required deploy settings are missing."""
    missing = []
    if not settings.config.deploy_target_user:
        missing.append("DEPLOY_TARGET_USER")
    if not settings.config.deploy_target_path:
        missing.append("DEPLOY_TARGET_PATH")
    if missing:
        raise ValueError(f"Missing required deploy config: {', '.join(missing)}")


def swap_command(remote_path):
    """Publish ``star_schema.db.new``, retaining one previous version.

    The ``.new`` check comes first, before anything is mutated. Every
    successful deploy consumes ``.new``, so an operator clearing this task in
    the Airflow UI afterwards runs it with no ``.new`` present. Setting the
    live database aside first and only then discovering ``.new`` is missing
    would leave the dashboard with no database at all.

    ``ln`` rather than ``mv`` for the aside, so the live file is never
    unlinked: the only observable change in the whole operation is the final
    rename. That rename is atomic and puts a new inode at the live path,
    which is what triggers the dashboard backend's hot-reload.

    The ``[ ! -f star_schema.db ]`` branch lets the first-ever deploy through
    -- there is nothing to set aside, so no ``.prev`` is created.
    """
    p = shlex.quote(str(remote_path))
    return (
        f"cd {p} "
        f'&& {{ [ -f star_schema.db.new ] || {{ echo "no star_schema.db.new to deploy" >&2; exit 1; }}; }} '
        f"&& {{ [ ! -f star_schema.db ] || ln -f star_schema.db star_schema.db.prev; }} "
        f"&& mv -f star_schema.db.new star_schema.db"
    )


def rollback_command(remote_path):
    """Restore ``star_schema.db.prev`` as the live database.

    One atomic rename, which simultaneously restores the previous version and
    unlinks the version being abandoned. ``.prev`` is therefore consumed, so
    a second rollback fails its precondition and changes nothing -- that is
    the "one previous version" rule enforcing itself.

    Rolling forward again is an ordinary ``igh_deployment`` run. The
    abandoned version is deliberately not parked in ``.new``: it would make
    rerunning the deploy DAG's swap task silently re-promote the exact
    version that was just rolled back from.
    """
    p = shlex.quote(str(remote_path))
    return (
        f"cd {p} "
        f'&& {{ [ -f star_schema.db.prev ] || {{ echo "no star_schema.db.prev to roll back to" >&2; exit 1; }}; }} '
        f"&& mv -f star_schema.db.prev star_schema.db"
    )


def run_remote(command, timeout=60):
    """Run a shell command on the dashboard server over SSH.

    Raises ``RuntimeError`` including the remote stderr on a non-zero exit,
    so the ``echo`` from a failed precondition inside ``command`` shows up in
    the Airflow task log rather than a bare exit code.
    """
    cmd = [
        "ssh",
        "-i",
        settings.config.deploy_ssh_key_path,
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{settings.config.deploy_target_user}@{settings.config.deploy_target_host}",
        command,
    ]

    logger.info("Running on %s: %s", settings.config.deploy_target_host, command)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"Remote command failed (rc={result.returncode}): {result.stderr.strip()}")
    return result
