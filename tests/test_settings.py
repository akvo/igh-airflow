"""Tests for PipelineConfig env parsing."""

import importlib


def _fresh_config(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("DEPLOY_AUTO_TRIGGER", raising=False)
    else:
        monkeypatch.setenv("DEPLOY_AUTO_TRIGGER", value)
    import config.settings as settings

    importlib.reload(settings)
    return settings.PipelineConfig()


def test_deploy_auto_trigger_defaults_false(monkeypatch):
    assert _fresh_config(monkeypatch, None).deploy_auto_trigger is False


def test_deploy_auto_trigger_parses_truthy(monkeypatch):
    assert _fresh_config(monkeypatch, "true").deploy_auto_trigger is True
    assert _fresh_config(monkeypatch, "1").deploy_auto_trigger is True
    assert _fresh_config(monkeypatch, "yes").deploy_auto_trigger is True
    assert _fresh_config(monkeypatch, "on").deploy_auto_trigger is True


def test_deploy_auto_trigger_parses_falsy(monkeypatch):
    assert _fresh_config(monkeypatch, "false").deploy_auto_trigger is False
    assert _fresh_config(monkeypatch, "no").deploy_auto_trigger is False
