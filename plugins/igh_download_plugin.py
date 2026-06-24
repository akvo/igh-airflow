"""IGH layer-database download plugin.

Serves the bronze/silver/gold SQLite databases to authenticated users so
data analysts can inspect each ETL layer. The FastAPI endpoint is added in
the next task; this module first defines the layer->path map and the
snapshot helper.
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

# The plugin lives in /opt/airflow/plugins while config lives in
# /opt/airflow/config. Add the project root so ``config.settings`` imports,
# mirroring the shim the DAGs use.
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import config

# Public layer name -> on-disk SQLite database path.
LAYER_PATHS: dict[str, str] = {
    "bronze": config.bronze_db_path,
    "silver": config.silver_db_path,
    "gold": config.gold_db_path,
}


def snapshot_db(src_path: str) -> str:
    """Return the path to a fresh, consistent copy of the SQLite DB.

    Uses SQLite's online backup API so the copy is transactionally
    consistent even if a transform DAG is writing to the source at the same
    moment. The source is opened read-only so a download can never block or
    corrupt a write. The caller owns the returned temp file and must delete
    it once it has been served.
    """
    fd, dst_path = tempfile.mkstemp(suffix=".db", prefix="igh_dl_")
    os.close(fd)
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(dst_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return dst_path
