"""Tests for the shared IGH Asset definitions."""

from airflow.sdk import Asset


def test_assets_have_expected_names():
    from dags.igh_assets import bronze_asset, gold_asset, silver_asset

    assert isinstance(bronze_asset, Asset)
    assert bronze_asset.name == "igh_bronze_db"
    assert silver_asset.name == "igh_silver_db"
    assert gold_asset.name == "igh_gold_db"
