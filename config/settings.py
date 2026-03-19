"""Centralized configuration settings for IGH Airflow DAGs."""

import os
from dataclasses import dataclass, field
from datetime import timedelta


def get_env(key: str, default: str) -> str:
    """Get environment variable with fallback to Airflow Variable."""
    value = os.getenv(key)
    if value:
        return value

    try:
        from airflow.models import Variable

        return Variable.get(key.lower(), default_var=default)
    except Exception:
        return default


@dataclass
class PipelineConfig:
    """Configuration for IGH data pipeline."""

    # Database paths
    bronze_db_path: str = field(
        default_factory=lambda: get_env("BRONZE_DB_PATH", "/opt/airflow/data/bronze/dataverse.db")
    )
    silver_db_path: str = field(
        default_factory=lambda: get_env("SILVER_DB_PATH", "/opt/airflow/data/silver/igh_silver.db")
    )
    production_db_path: str = field(
        default_factory=lambda: get_env("PRODUCTION_DB_PATH", "/opt/airflow/data/production/igh.db")
    )

    # Retry configuration
    retries: int = 2
    retry_delay: timedelta = field(default_factory=lambda: timedelta(minutes=5))


# Singleton instance for easy import
config = PipelineConfig()
