# Self-Hosted Production Deployment

Production deployment of the IGH Airflow pipeline using Docker Compose
with Traefik reverse proxy and automatic Let's Encrypt TLS certificates.

## Prerequisites

- Docker and Docker Compose (v2)
- A domain name with DNS A record pointing to the server
- Ports 80 and 443 open on the server

## Setup

1. Copy the environment template and fill in production values:

   ```bash
   cp .env.example .env
   ```

2. Generate security keys:

   ```bash
   # Fernet key (encryption at rest)
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

   # API secret key (JWT signing between services)
   python -c "import secrets; print(secrets.token_hex(32))"

   # JWT secret (internal API authentication)
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

   Set the generated values in `.env`:

   - `AIRFLOW__CORE__FERNET_KEY`
   - `AIRFLOW__API__SECRET_KEY`
   - `AIRFLOW__API_AUTH__JWT_SECRET`

3. Configure your domain and Let's Encrypt email in `.env`:

   ```
   AIRFLOW_DOMAIN=airflow.example.com
   LETSENCRYPT_ACME_EMAIL=admin@example.com
   ```

4. Set strong passwords for PostgreSQL, Redis, and the Airflow admin user.

5. Fill in the Dataverse API credentials.

## Deployment

Run the install script for the initial deployment:

```bash
./install.sh
```

This pulls the latest code, builds the Docker image, and starts all
services. Verify the deployment:

```bash
docker compose ps
docker compose logs -f airflow-apiserver
```

The Airflow UI will be available at `https://<AIRFLOW_DOMAIN>` once the
API server health check passes (may take up to two minutes on first
start).

## Operations

### Update (pull, rebuild, restart)

```bash
./update.sh
```

Pulls the latest code from git, rebuilds the Docker image from scratch,
then restarts all services.

### Quick restart (no rebuild)

```bash
./restart.sh
```

Restarts running containers without rebuilding.

### Celery monitoring with Flower

```bash
docker compose --profile flower up -d
```

Flower is available at `http://<server-ip>:5555`.

### Viewing logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f airflow-scheduler
docker compose logs -f airflow-worker
```

### Running Airflow CLI commands

```bash
docker compose run --rm airflow-cli airflow dags list
```

Or use the debug profile:

```bash
docker compose --profile debug run --rm airflow-cli bash
```

## Architecture

| Service               | Description                                          |
|-----------------------|------------------------------------------------------|
| `traefik`             | Reverse proxy with automatic TLS via Let's Encrypt   |
| `postgres`            | PostgreSQL 16 metadata database                      |
| `redis`               | Redis 7.2 Celery message broker                      |
| `airflow-apiserver`   | Airflow API server and web UI                        |
| `airflow-scheduler`   | Schedules and triggers DAG runs                      |
| `airflow-worker`      | Celery worker that executes tasks                    |
| `airflow-dag-processor` | Parses DAG files                                   |
| `airflow-triggerer`   | Handles deferred/async operators                     |
| `airflow-init`        | One-shot: runs DB migrations and creates admin user  |
| `flower`              | Celery monitoring UI (optional, `flower` profile)    |
| `airflow-cli`         | Airflow CLI access (optional, `debug` profile)       |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AIRFLOW_IMAGE_NAME` | Docker image name (default: `igh-airflow:latest`) |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | PostgreSQL database name |
| `REDIS_PASSWORD` | Redis password for Celery broker |
| `_AIRFLOW_WWW_USER_USERNAME` | Airflow admin username |
| `_AIRFLOW_WWW_USER_PASSWORD` | Airflow admin password |
| `AIRFLOW__CORE__FERNET_KEY` | Fernet encryption key |
| `AIRFLOW__API__SECRET_KEY` | API secret key for JWT signing |
| `AIRFLOW__API_AUTH__JWT_SECRET` | JWT secret for internal API auth |
| `AIRFLOW_DOMAIN` | Domain for Traefik routing and TLS |
| `LETSENCRYPT_ACME_EMAIL` | Email for Let's Encrypt certificate registration |
| `SLACK_WEBHOOK_URL` | Slack webhook URL for alerts (optional) |
| `BRONZE_DB_PATH` | Path to Bronze SQLite database |
| `SILVER_DB_PATH` | Path to Silver SQLite database |
| `DEPLOY_SSH_KEY_PATH_HOST` | Host path to SSH key for Docker mount |
| `DEPLOY_TARGET_HOST` | Dashboard server host |
| `DEPLOY_TARGET_USER` | SSH user on dashboard server |
| `DEPLOY_TARGET_PATH` | Remote path for `star_schema.db` |
| `INGESTION_SCHEDULE` | Cron schedule for ingestion DAG (default: `0 2 * * *`) |
| `TRANSFORM_SCHEDULE` | Cron schedule for transform DAG (default: `0 4 * * *`) |
| `DEPLOYMENT_SCHEDULE` | Cron schedule for deployment DAG (default: `0 6 * * *`) |
| `DATAVERSE_API_URL` | Microsoft Dataverse API endpoint |
| `DATAVERSE_CLIENT_ID` | OAuth client ID |
| `DATAVERSE_CLIENT_SECRET` | OAuth client secret |
| `DATAVERSE_SCOPE` | OAuth scope |

## Data Persistence

Data is stored in named Docker volumes:

| Volume | Mount Point | Purpose |
|--------|-------------|---------|
| `igh-airflow-postgres` | `/var/lib/postgresql/data` | Airflow metadata database |
| `igh-airflow-logs` | `/opt/airflow/logs` | Airflow task logs |
| `igh-airflow-data` | `/opt/airflow/data` | Pipeline data (bronze, silver, production) |
| `igh-airflow-letsencrypt` | `/letsencrypt` | TLS certificates |
