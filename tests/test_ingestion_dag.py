"""Tests for IGH Ingestion DAG."""


def test_dag_loads():
    """Test that the ingestion DAG loads without errors."""
    from dags.igh_ingestion_dag import dag

    assert dag is not None
    assert dag.dag_id == "igh_ingestion"


def test_dag_has_correct_tags():
    """Test that the DAG has the expected tags."""
    from dags.igh_ingestion_dag import dag

    assert "igh" in dag.tags
    assert "ingestion" in dag.tags


def test_dag_is_manual_only():
    """Test that the DAG has no schedule (manual trigger only)."""
    from dags.igh_ingestion_dag import dag

    assert dag.schedule is None


def test_dag_has_tasks():
    """Test that the DAG has the expected tasks."""
    from dags.igh_ingestion_dag import dag

    task_ids = [task.task_id for task in dag.tasks]
    assert "sync_dataverse" in task_ids


def test_dag_task_count():
    """Test that the DAG has the expected number of tasks."""
    from dags.igh_ingestion_dag import dag

    assert len(dag.tasks) == 1
