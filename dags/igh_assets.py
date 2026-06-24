"""Shared Airflow Asset definitions for the IGH ETL pipeline.

These Assets are the trigger baton between the pipeline DAGs:

- ``igh_ingestion`` produces ``bronze_asset`` -> schedules ``igh_transform``
- ``igh_transform`` produces ``silver_asset`` then ``gold_asset``
- ``gold_asset`` optionally schedules ``igh_deployment`` (see DEPLOY_AUTO_TRIGGER)

The Assets are name-only: their identity is the name, not a filesystem path,
so producers and consumers stay decoupled from where the databases live.
"""

from airflow.sdk import Asset

bronze_asset = Asset(name="igh_bronze_db")
silver_asset = Asset(name="igh_silver_db")
gold_asset = Asset(name="igh_gold_db")
