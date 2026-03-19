"""Tests for IGH Transform DAG."""

from airflow.providers.standard.operators.python import PythonOperator


def test_dag_loads():
    """Test that the transform DAG loads without errors."""
    from dags.igh_transform_dag import dag

    assert dag is not None
    assert dag.dag_id == "igh_transform"


def test_dag_has_correct_tags():
    """Test that the DAG has the expected tags."""
    from dags.igh_transform_dag import dag

    assert "igh" in dag.tags
    assert "transform" in dag.tags


def test_dag_is_manual_only():
    """Test that the DAG has no schedule (manual trigger only)."""
    from dags.igh_transform_dag import dag

    assert dag.schedule is None


def test_dag_has_tasks():
    """Test that the DAG has the expected tasks."""
    from dags.igh_transform_dag import dag

    task_ids = {task.task_id for task in dag.tasks}
    assert task_ids == {"bronze_to_silver", "silver_to_gold"}


def test_dag_task_count():
    """Test that the DAG has the expected number of tasks."""
    from dags.igh_transform_dag import dag

    assert len(dag.tasks) == 2


def test_dag_task_types():
    """Test that tasks have the correct operator types."""
    from dags.igh_transform_dag import dag

    assert isinstance(dag.get_task("bronze_to_silver"), PythonOperator)
    assert isinstance(dag.get_task("silver_to_gold"), PythonOperator)


def test_dag_task_dependencies():
    """Test that bronze_to_silver feeds into silver_to_gold."""
    from dags.igh_transform_dag import dag

    bronze_to_silver = dag.get_task("bronze_to_silver")
    silver_to_gold = dag.get_task("silver_to_gold")

    assert bronze_to_silver in silver_to_gold.upstream_list
