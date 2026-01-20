FROM apache/airflow:3.1.0-python3.11

USER root

# Install system dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY --chown=airflow:root pyproject.toml uv.lock /opt/airflow/
WORKDIR /opt/airflow

# Export requirements as root (uv needs to read the files)
RUN uv export --frozen --no-dev --no-emit-project > requirements.txt \
    && chown airflow:root requirements.txt

# Switch to airflow user and install packages
USER airflow
RUN pip install --upgrade -r requirements.txt && rm requirements.txt

# Copy DAGs and project files
COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root plugins/ /opt/airflow/plugins/
COPY --chown=airflow:root config/ /opt/airflow/config/
COPY --chown=airflow:root utils/ /opt/airflow/utils/

# Copy entrypoint
COPY --chown=airflow:root docker/entrypoint.sh /entrypoint-custom.sh
RUN chmod +x /entrypoint-custom.sh

# Enable automatic database migration on container startup
# User creation is NOT enabled here for security - credentials must be
# provided at deployment time via environment variables or secrets
ENV _AIRFLOW_DB_MIGRATE="true"

ENTRYPOINT ["/entrypoint-custom.sh"]
CMD ["api-server"]
