FROM apache/airflow:2.8.0-python3.11

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Copy requirements and install Python dependencies
COPY --chown=airflow:root pyproject.toml /opt/airflow/
RUN pip install --no-cache-dir requests apache-airflow-providers-slack

# Copy DAGs and project files
COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root plugins/ /opt/airflow/plugins/
COPY --chown=airflow:root config/ /opt/airflow/config/
COPY --chown=airflow:root utils/ /opt/airflow/utils/

# Copy entrypoint
COPY --chown=airflow:root docker/entrypoint.sh /entrypoint-custom.sh
RUN chmod +x /entrypoint-custom.sh

ENTRYPOINT ["/entrypoint-custom.sh"]
CMD ["webserver"]
