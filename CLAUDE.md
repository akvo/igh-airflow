# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

This is an Apache Airflow 3.1.6 orchestration project for the IGH Data Pipeline using CeleryExecutor. It manages three main workflows:
- **Ingestion**: Sync data from Microsoft Dataverse to Bronze SQLite database
- **Transform**: Process data from Bronze to Silver and Gold layers
- **Deployment**: Deploy validated data to production

## Development Commands

### Environment Setup

```bash
# Install dependencies with UV
uv sync

# Install with dev dependencies
uv sync --all-groups
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_ingestion_dag.py -v

# Run with coverage
uv run pytest tests/ --cov=dags --cov=config
```

### Linting

```bash
# Check code style
uv run ruff check dags/ config/ plugins/ tests/

# Auto-fix issues
uv run ruff check --fix dags/ config/ plugins/ tests/

# Format code
uv run ruff format dags/ config/ plugins/ tests/
```

### Local Development with Docker

```bash
# Start Airflow (builds custom image)
docker compose up -d

# Force rebuild image
docker compose build --no-cache

# View logs
docker compose logs -f

# Access shell
docker compose exec airflow-apiserver bash

# List DAGs
docker compose exec airflow-apiserver airflow dags list

# Stop Airflow
docker compose down

# Run with Flower (Celery monitoring)
docker compose --profile flower up -d
```

### Simulating the dashboard server

The deploy and rollback DAGs talk to a remote machine over SSH, so the only
way to exercise them for real is against an SSH host. The `dashboard-sim`
profile provides a throwaway one on the compose network — an `alpine` +
`openssh` container. It is behind a profile, so a plain `docker compose up -d`
never starts it.

```bash
# 1. Generate the throwaway keypair FIRST. If you start the stack before
#    ./ssh exists, Docker creates it root-owned and ssh-keygen then fails.
mkdir -p ssh && ssh-keygen -t ed25519 -f ssh/id_rsa -N "" -q && chmod 600 ssh/id_rsa

# 2. A gold DB to deploy. Use a real one if you have it; a stand-in is
#    otherwise fine, since the swap and rollback never read the contents.
mkdir -p data/gold
uv run python -c "import sqlite3; sqlite3.connect('data/gold/star_schema.db').execute('create table t(x)')"

# 3. Start the stack together with the simulated dashboard server.
DEPLOY_TARGET_HOST=dashboard-sim \
DEPLOY_TARGET_USER=deployer \
DEPLOY_TARGET_PATH=/srv/dashboard \
  docker compose --profile dashboard-sim up -d

# 4. Unpause the DAGs you want to drive.
docker compose exec airflow-apiserver airflow dags unpause igh_deployment
docker compose exec airflow-apiserver airflow dags unpause igh_rollback
```

Inspect the simulated deploy directory at any point — `-i` shows inodes,
which is how you confirm the retention is a hardlink and not a copy:

```bash
docker compose exec dashboard-sim sh -c 'cd /srv/dashboard && ls -li star_schema.db*'
```

What each step should produce:

| Action | Expected state |
|--------|----------------|
| Trigger `igh_deployment` (first time) | `star_schema.db` only — no `.prev` |
| Change the gold DB, trigger again | live is the new version; `.prev` holds the old one **at the inode the live file had before** |
| Trigger `igh_rollback` | live is the old version again, `.prev` gone |
| Trigger `igh_rollback` a second time | task **fails**: `no star_schema.db.prev to roll back to`; directory unchanged |
| Clear only `swap_remote_db` and let it rerun | task **fails**: `no star_schema.db.new to deploy`; **live DB still intact** |

That last row is the one worth re-running after any change to the swap
command: it is the case where a set-aside-then-swap ordering would leave the
dashboard with no database at all.

Two things that will trip you up:

- The key must be readable by the container user. `.env` sets
  `AIRFLOW_UID=1000`; if that does not match the owner of `ssh/id_rsa`, `ssh`
  rejects the key.
- `swap_remote_db` inherits `retries: 1` with a 5-minute delay, so a cleared
  swap task sits in `up_for_retry` for five minutes before it goes red. The
  failure itself is immediate — check the task log rather than waiting on the
  final state.

The sim's login shell is busybox `ash`, not bash, so a passing run also
confirms the command strings are portable POSIX shell — which is what `ssh`
hands to whatever login shell the real dashboard server runs.

## Architecture

### DAG Pipeline

The pipeline auto-chains via Airflow Assets. Ingestion is manual; transform
runs on the bronze Asset; deployment is manual by default or auto-runs on
the gold Asset when DEPLOY_AUTO_TRIGGER=true. Asset triggering requires the
consuming DAG to be unpaused.

```
igh_ingestion (manual)          sync_dataverse        -> Asset: igh_bronze_db
igh_transform (on igh_bronze_db) bronze_to_silver     -> Asset: igh_silver_db
                                 silver_to_gold        -> Asset: igh_gold_db
igh_deployment (manual or on igh_gold_db) scp_gold_db >> swap_remote_db
igh_rollback (manual only)      rollback_remote_db
```

### Project Structure

```
igh-airflow/
├── dags/                    # Airflow DAG definitions
│   ├── igh_ingestion_dag.py # Dataverse sync using igh-data-sync
│   ├── igh_transform_dag.py # Bronze→Silver→Gold
│   ├── igh_deployment_dag.py # Production deployment
│   ├── igh_rollback_dag.py  # Restore the previous gold DB on the dashboard
│   ├── igh_deploy_remote.py # Shared SSH publish protocol + command builders
│   └── igh_assets.py        # Shared Asset definitions (trigger baton)
├── plugins/                 # Airflow plugins
│   └── igh_download_plugin.py # Authenticated layer-DB download endpoint
├── config/                  # Configuration modules
│   └── settings.py          # PipelineConfig dataclass
├── data/                    # Data directories (bronze/silver/production)
├── logs/                    # Airflow logs
├── tests/                   # Unit tests
├── docker/                  # Production Docker files
│   ├── Dockerfile           # Airflow 3.1.6 + igh-data-sync
│   └── entrypoint.sh        # Custom entrypoint
├── docker-compose.yml       # Local development (CeleryExecutor)
└── pyproject.toml           # Project configuration
```

### Key Modules

- **config/settings.py**: Centralized configuration with `PipelineConfig` dataclass. Uses `get_env()` to read from environment variables with fallback to Airflow Variables.
- **dags/igh_ingestion_dag.py**: Uses `igh-data-sync` library to sync from Dataverse. Exposes a boolean DAG param `update_mode` (default `False`). When `False` the task deletes the existing bronze DB before syncing (fresh build, matching `sync-and-run-etl.sh`); when `True` it keeps the bronze DB and syncs incrementally.

### Layer Downloads

`plugins/igh_download_plugin.py` registers a FastAPI sub-app on the API
server at `GET /igh/download/{layer}` (`layer` ∈ bronze/silver/gold). It
streams a consistent SQLite snapshot (online-backup API) as an attachment,
authenticated via the same login as the Airflow UI (the `_token` JWT
cookie). Returns 404 if that layer hasn't been produced yet.

The plugin also adds **Downloads → Bronze/Silver/Gold DB** entries to the
Airflow UI navigation (`appbuilder_menu_items`), each a link straight to
`/igh/download/{layer}` that opens in a new tab and downloads. Two Airflow
UI constraints shaped this: `external_views` are rendered in a sandboxed
iframe (no `allow-downloads`) that blocks the download, so plain menu links
are used instead; and Airflow renders plugin menu items as real links only
when there are at least two, so all three layers are listed (a single item
collapses into a non-navigating button).

### Gold DB Retention and Rollback

The dashboard server keeps one previous gold database. `swap_remote_db`
hardlinks the outgoing `star_schema.db` to `star_schema.db.prev` before the
atomic rename that publishes `star_schema.db.new`, and `igh_rollback`
renames `.prev` back over the live file.

Both commands check their precondition *before* mutating anything, so a
swap with no `.new` (which is the state after every successful deploy) and a
second rollback with no `.prev` both fail loudly and leave the directory
untouched. Rolling forward after a rollback is an ordinary `igh_deployment`
run — the abandoned version is not retained remotely.

To exercise this workflow for real without a remote machine, see
[Simulating the dashboard server](#simulating-the-dashboard-server).

`igh_rollback` is manual-trigger only. Because
`DAGS_ARE_PAUSED_AT_CREATION` is `true`, **unpause it once after deploying**:
a paused DAG accepts a trigger but its run sits queued, which is not what
you want to discover during an incident.

## Configuration

### Environment Variables (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `AIRFLOW_IMAGE_NAME` | Docker image name | `igh-airflow:latest` |
| `AIRFLOW_UID` | Linux user ID for Airflow | `50000` |
| `REDIS_PASSWORD` | Redis password for Celery broker | `redispass` |
| `_AIRFLOW_WWW_USER_USERNAME` | Airflow UI username | `airflow` |
| `_AIRFLOW_WWW_USER_PASSWORD` | Airflow UI password | `airflow` |
| `AIRFLOW__CORE__FERNET_KEY` | Fernet encryption key | - |
| `AIRFLOW__API__SECRET_KEY` | API secret key for JWT | - |
| `BRONZE_DB_PATH` | Bronze database location | `/opt/airflow/data/bronze/dataverse.db` |
| `SILVER_DB_PATH` | Silver database location | `/opt/airflow/data/silver/igh_silver.db` |
| `GOLD_DB_PATH` | Gold star-schema database location | `/opt/airflow/data/gold/star_schema.db` |
| `DEPLOY_SSH_KEY_PATH` | SSH private key path inside container | `/opt/airflow/ssh/id_rsa` |
| `DEPLOY_TARGET_HOST` | Dashboard server host (`local` or empty to skip) | `local` (dev compose) |
| `DEPLOY_TARGET_USER` | SSH user on dashboard server | - |
| `DEPLOY_TARGET_PATH` | Remote path for `star_schema.db` | - |
| `DEPLOY_SSH_KEY_PATH_HOST` | Host path to SSH key (Docker mount, self-hosted only) | `./ssh/id_rsa` |
| `DEPLOY_AUTO_TRIGGER` | Auto-run deployment on the gold Asset (`true`) vs. manual (`false`) | `false` |
| `DATAVERSE_API_URL` | Dataverse API endpoint URL | - |
| `DATAVERSE_CLIENT_ID` | OAuth client ID | - |
| `DATAVERSE_CLIENT_SECRET` | OAuth client secret | - |
| `DATAVERSE_SCOPE` | OAuth scope | - |

### Generating Security Keys

```bash
# Generate Fernet key
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate API secret key
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

### Airflow Variables (Admin → Variables)

Airflow Variables are used as fallback when environment variables are not set:

| Variable | Description |
|----------|-------------|
| `DATAVERSE_API_URL` | Fallback for Dataverse API endpoint URL |
| `DATAVERSE_CLIENT_ID` | Fallback for OAuth client ID |
| `DATAVERSE_CLIENT_SECRET` | Fallback for OAuth client secret |
| `DATAVERSE_SCOPE` | Fallback for OAuth scope |

## Testing

Tests verify DAG structure, task counts, and dependencies without running actual tasks.

```bash
# All tests should pass
uv run pytest tests/ -v
```

## Common Tasks

### Adding a New DAG

1. Create `dags/new_dag.py` following existing patterns
2. Add tests in `tests/test_new_dag.py`
3. Run tests: `uv run pytest tests/test_new_dag.py -v`

### Modifying Configuration

1. Update `config/settings.py` for new settings
2. Update `.env.example` for new environment variables
3. Update this CLAUDE.md with new variables

### Debugging DAG Issues

1. Check Airflow logs: `docker compose logs airflow-scheduler`
2. List DAGs: `docker compose exec airflow-apiserver airflow dags list`
3. Test DAG loading: `docker compose exec airflow-apiserver python -c "from dags.igh_ingestion_dag import dag; print(dag)"`
4. Check Celery workers: `docker compose logs airflow-worker`
5. Monitor Celery with Flower: `docker compose --profile flower up -d` then visit http://localhost:5555

## Troubleshooting

### Redis/Celery Compatibility

The project pins `redis>=5.0.0,<6.0.0` in `pyproject.toml` due to compatibility issues between `redis 6.x` and `kombu` (Celery's transport library). If you see errors like:

```
AttributeError: module 'redis' has no attribute 'client'
```

Ensure the redis package is pinned to version 5.x and rebuild the Docker image:

```bash
docker compose build --no-cache && docker compose up -d
```
