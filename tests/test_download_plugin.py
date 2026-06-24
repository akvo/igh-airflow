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
