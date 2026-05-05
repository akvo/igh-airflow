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


def test_dag_has_update_mode_param():
    """Test that the DAG declares an `update_mode` boolean param defaulting to False."""
    from dags.igh_ingestion_dag import dag

    assert "update_mode" in dag.params
    param = dag.params.get_param("update_mode")
    # Param.value returns the resolved/default value.
    assert param.value is False
    # Schema check: ensure it's declared as boolean so the UI renders a checkbox.
    assert param.schema.get("type") == "boolean"
