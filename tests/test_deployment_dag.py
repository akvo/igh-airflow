"""Tests for IGH Deployment DAG."""


def test_dag_loads():
    """Test that the deployment DAG loads without errors."""
    from dags.igh_deployment_dag import dag

    assert dag is not None
    assert dag.dag_id == "igh_deployment"


def test_dag_has_correct_tags():
    """Test that the DAG has the expected tags."""
    from dags.igh_deployment_dag import dag

    assert "igh" in dag.tags
    assert "deployment" in dag.tags


def test_dag_is_manual_only():
    """Test that the DAG has no schedule (manual trigger only)."""
    from dags.igh_deployment_dag import dag

    assert dag.schedule is None


def test_dag_has_tasks():
    """Test that the DAG has the expected tasks."""
    from dags.igh_deployment_dag import dag

    task_ids = [task.task_id for task in dag.tasks]
    assert "deploy_to_production" in task_ids


def test_dag_task_count():
    """Test that the DAG has the expected number of tasks."""
    from dags.igh_deployment_dag import dag

    assert len(dag.tasks) == 1
