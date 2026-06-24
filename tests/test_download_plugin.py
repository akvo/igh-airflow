"""Tests for the IGH layer-download plugin."""

import os
import sqlite3


def test_snapshot_db_copies_contents(tmp_path):
    src = tmp_path / "src.db"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()

    from igh_download_plugin import snapshot_db

    dst = snapshot_db(str(src))
    try:
        assert dst != str(src)
        check = sqlite3.connect(dst)
        assert check.execute("SELECT x FROM t").fetchone()[0] == 42
        check.close()
    finally:
        os.remove(dst)


def test_layer_paths_cover_all_layers():
    from igh_download_plugin import LAYER_PATHS

    assert set(LAYER_PATHS) == {"bronze", "silver", "gold"}


def _client():
    import igh_download_plugin as dl
    from fastapi.testclient import TestClient

    return TestClient(dl.app, raise_server_exceptions=True), dl


def test_unauthenticated_request_is_rejected():
    client, _ = _client()
    resp = client.get("/download/silver")
    assert resp.status_code == 401  # no JWT cookie/header -> "Not authenticated"


def test_unknown_layer_returns_404(monkeypatch):
    from airflow.api_fastapi.core_api.security import get_user

    client, dl = _client()
    dl.app.dependency_overrides[get_user] = lambda: object()
    try:
        resp = client.get("/download/platinum")
        assert resp.status_code == 404
    finally:
        dl.app.dependency_overrides.clear()


def test_missing_database_returns_404(monkeypatch, tmp_path):
    from airflow.api_fastapi.core_api.security import get_user

    client, dl = _client()
    dl.app.dependency_overrides[get_user] = lambda: object()
    monkeypatch.setitem(dl.LAYER_PATHS, "silver", str(tmp_path / "nope.db"))
    try:
        resp = client.get("/download/silver")
        assert resp.status_code == 404
    finally:
        dl.app.dependency_overrides.clear()


def test_authenticated_download_streams_db(monkeypatch, tmp_path):
    import sqlite3

    from airflow.api_fastapi.core_api.security import get_user

    src = tmp_path / "silver.db"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (7)")
    conn.commit()
    conn.close()

    client, dl = _client()
    dl.app.dependency_overrides[get_user] = lambda: object()
    monkeypatch.setitem(dl.LAYER_PATHS, "silver", str(src))
    try:
        resp = client.get("/download/silver")
        assert resp.status_code == 200
        assert "attachment" in resp.headers["content-disposition"]
        assert "igh_silver.db" in resp.headers["content-disposition"]
        # Body is a valid SQLite file starting with the standard header.
        assert resp.content[:16] == b"SQLite format 3\x00"
    finally:
        dl.app.dependency_overrides.clear()
