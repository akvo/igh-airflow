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

from airflow.api_fastapi.core_api.security import GetUserDep
from airflow.plugins_manager import AirflowPlugin
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

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


app = FastAPI(title="IGH Downloads")


@app.get("/download/{layer}")
def download_layer(layer: str, user: GetUserDep) -> FileResponse:
    """Stream a consistent snapshot of the requested layer's database.

    The ``user: GetUserDep`` parameter forces authentication: the core API
    dependency reads the JWT from the Authorization header or the ``_token``
    cookie (which the Airflow UI sets on login) and rejects unauthenticated
    requests with 401/403. Any logged-in Airflow user may download.
    """
    src_path = LAYER_PATHS.get(layer)
    if src_path is None:
        raise HTTPException(status_code=404, detail=f"Unknown layer: {layer!r}")
    if not os.path.exists(src_path):
        raise HTTPException(status_code=404, detail=f"No {layer} database has been produced yet")

    # Stream a consistent temp snapshot, then delete it once the response is
    # fully sent (FileResponse runs the background task after streaming).
    tmp_path = snapshot_db(src_path)
    return FileResponse(
        tmp_path,
        media_type="application/octet-stream",
        filename=f"igh_{layer}.db",
        background=BackgroundTask(os.remove, tmp_path),
    )


class IGHDownloadPlugin(AirflowPlugin):
    name = "igh_download"
    fastapi_apps = [
        {
            "app": app,
            "url_prefix": "/igh",
            "name": "IGH Downloads",
        }
    ]
