"""Tests for Slack alerting utilities."""

from unittest.mock import MagicMock, patch


def test_send_failure_alert_formats_message(mock_context):
    """Test that failure alert formats message correctly."""
    from utils.slack_alerts import send_failure_alert

    with patch("utils.slack_alerts.send_slack_message") as mock_send:
        mock_send.return_value = True
        send_failure_alert(mock_context)

        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]

        assert "Task Failed" in message
        assert "test_dag" in message
        assert "test_task" in message


def test_send_success_alert_formats_message(mock_context):
    """Test that success alert formats message correctly."""
    from utils.slack_alerts import send_success_alert

    with patch("utils.slack_alerts.send_slack_message") as mock_send:
        mock_send.return_value = True
        send_success_alert(mock_context)

        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]

        assert "Completed Successfully" in message
        assert "test_dag" in message


def test_send_slack_message_without_webhook(monkeypatch):
    """Test that send_slack_message handles missing webhook gracefully."""
    from utils.slack_alerts import send_slack_message

    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    with patch("utils.slack_alerts.get_slack_webhook_url", return_value=None):
        result = send_slack_message("Test message")
        assert result is False


def test_send_slack_message_with_webhook(monkeypatch):
    """Test that send_slack_message sends to webhook."""
    from utils.slack_alerts import send_slack_message

    with patch("requests.post") as mock_post:
        mock_post.return_value.raise_for_status = MagicMock()
        result = send_slack_message("Test message", webhook_url="https://hooks.slack.com/test")

        assert result is True
        mock_post.assert_called_once()
