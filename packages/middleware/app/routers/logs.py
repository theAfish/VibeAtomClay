from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import glob
import os
import asyncio
import logging
import time
from ..config import LOGS_DIR
from ..services import ensure_workspace_dirs

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/logs/stream")
async def stream_logs():
    ensure_workspace_dirs()
    
    # Wait for a log file to appear (timeout 10s)
    start_time = time.time()
    latest_file = None
    
    while time.time() - start_time < 10:
        list_of_files = glob.glob(str(LOGS_DIR / "*.log"))
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
