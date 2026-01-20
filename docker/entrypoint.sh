#!/bin/bash
set -e

# Delegate to the official Airflow entrypoint for proper signal handling,
# OpenShift compatibility, and database/broker availability checks.
exec /entrypoint "${@}"
