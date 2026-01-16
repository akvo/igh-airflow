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


def test_dag_has_tasks():
    """Test that the DAG has the expected tasks."""
    from dags.igh_deployment_dag import dag

    task_ids = [task.task_id for task in dag.tasks]
    assert "wait_for_transform" in task_ids
    assert "verify_silver_database" in task_ids
    assert "deploy_to_production" in task_ids
    assert "verify_production_database" in task_ids


def test_dag_task_count():
    """Test that the DAG has the expected number of tasks."""
    from dags.igh_deployment_dag import dag

    assert len(dag.tasks) == 4


def test_dag_task_dependencies():
    """Test that tasks have correct dependencies."""
    from dags.igh_deployment_dag import dag

    verify_silver = dag.get_task("verify_silver_database")
    deploy = dag.get_task("deploy_to_production")
    verify_production = dag.get_task("verify_production_database")

    # verify_silver should be upstream of deploy
    assert verify_silver in deploy.upstream_list
    # deploy should be upstream of verify_production
    assert deploy in verify_production.upstream_list
