from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
import glob
import os
import asyncio
import logging
import time
import json
from datetime import datetime
from ..config import get_session_dirs
from ..services import ensure_workspace_dirs, get_last_session_id, set_last_session_id

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/logs/stream")
async def stream_logs():
    session_id = get_last_session_id()
    if not session_id:
        async def empty_gen():
            yield ": No active session\n\n"
        return StreamingResponse(empty_gen(), media_type="text/event-stream")
    
    ensure_workspace_dirs(session_id)
    logs_dir = get_session_dirs(session_id)['logs']
    
    # Wait for a log file to appear (timeout 10s)
    start_time = time.time()
    latest_file = None
    
    while time.time() - start_time < 10:
        list_of_files = glob.glob(str(logs_dir / f"*_{session_id}.log"))
        if list_of_files:
            latest_file = max(list_of_files, key=os.path.getctime)
            break
        await asyncio.sleep(0.5)

    if not latest_file:
        # If no logs yet, just return empty stream or wait? 
        # Better to return error or wait. Let's return a comment.
        async def empty_gen():
            yield ": No logs found\n\n"
        return StreamingResponse(empty_gen(), media_type="text/event-stream")

    async def log_generator():
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                # Go to the end of the file to only stream new logs
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        yield f"data: {line.strip()}\n\n"
                    else:
                        await asyncio.sleep(0.1)
        except Exception as e:
            yield f"data: Error reading log: {str(e)}\n\n"

    return StreamingResponse(log_generator(), media_type="text/event-stream")


@router.post("/logs/operation")
async def write_operation_log(payload: dict = Body(...)):
    """Append a UI operation entry (or entries) to a session log file as JSON Lines.

    Expected payload shapes:
    - { "entry": {..}, "sessionId": "s_xxx", "userId": "u_xxx" }
    - { "entries": [{..}, {..}], "sessionId": "s_xxx", "userId": "u_xxx" }
    If sessionId is missing, falls back to the last known session; if none, uses 'ui'.
    """
    try:
        session_id = payload.get("sessionId") or get_last_session_id() or "ui"
        user_id = payload.get("userId")
        if session_id and session_id != "ui":
            set_last_session_id(session_id)

        ensure_workspace_dirs(session_id)
        logs_dir = get_session_dirs(session_id)["logs"]
        os.makedirs(logs_dir, exist_ok=True)

        # File name pattern compatible with /logs/stream lookup
        # It searches for *_{session_id}.log
        date_prefix = datetime.utcnow().strftime("%Y%m%d")
        file_path = os.path.join(logs_dir, f"operations_{date_prefix}_{session_id}.log")

        entries = []
        if "entry" in payload and isinstance(payload["entry"], dict):
            entries = [payload["entry"]]
        elif "entries" in payload and isinstance(payload["entries"], list):
            entries = payload["entries"]

        # Enrich entries with session/user if missing
        enriched = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            ee = dict(e)
            ee.setdefault("metadata", {})
            ee["metadata"].setdefault("sessionId", session_id)
            if user_id:
                ee["metadata"].setdefault("userId", user_id)
            enriched.append(ee)

        if not enriched:
            return {"status": "no-op"}

        with open(file_path, "a", encoding="utf-8") as f:
            for e in enriched:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

        return {"status": "ok", "written": len(enriched), "file": file_path}
    except Exception as e:
        logger.exception("Failed to write operation log")
        raise HTTPException(status_code=500, detail=f"Failed to write log: {e}")
