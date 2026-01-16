"""Tests for IGH Transform DAG."""


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


def test_dag_has_tasks():
    """Test that the DAG has the expected tasks."""
    from dags.igh_transform_dag import dag

    task_ids = [task.task_id for task in dag.tasks]
    assert "wait_for_ingestion" in task_ids
    assert "bronze_to_silver" in task_ids
    assert "silver_to_gold" in task_ids


def test_dag_task_count():
    """Test that the DAG has the expected number of tasks."""
    from dags.igh_transform_dag import dag

    assert len(dag.tasks) == 3


def test_dag_task_dependencies():
    """Test that tasks have correct dependencies."""
    from dags.igh_transform_dag import dag

    bronze_to_silver = dag.get_task("bronze_to_silver")
    silver_to_gold = dag.get_task("silver_to_gold")

    # bronze_to_silver should be upstream of silver_to_gold
    assert bronze_to_silver in silver_to_gold.upstream_list
