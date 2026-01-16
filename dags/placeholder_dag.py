"""Placeholder DAG to verify Airflow setup."""

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


def hello_world():
    print("Hello from IGH Airflow!")
    return "success"


with DAG(
    dag_id="placeholder",
    description="Placeholder DAG to verify Airflow setup",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["test"],
) as dag:
    task = PythonOperator(
        task_id="hello_world",
        python_callable=hello_world,
    )
