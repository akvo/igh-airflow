#!/bin/bash
set -e

# Initialize database if needed
if [[ "$1" == "webserver" ]] || [[ "$1" == "scheduler" ]]; then
    airflow db check || airflow db migrate
fi

# Create admin user if webserver and user doesn't exist
if [[ "$1" == "webserver" ]]; then
    airflow users list | grep -q admin || \
        airflow users create \
            --username "${AIRFLOW_ADMIN_USER:-admin}" \
            --firstname Admin \
            --lastname User \
            --role Admin \
            --email admin@example.com \
            --password "${AIRFLOW_ADMIN_PASSWORD:-admin}" || true
fi

# Execute the command
exec airflow "$@"
