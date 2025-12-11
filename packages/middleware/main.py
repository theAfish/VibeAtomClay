from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import requests
import httpx
import uuid
import os
import asyncio
import glob
import logging
from pathlib import Path

app = FastAPI(title="AtomClay Backend", description="Middle-layer API for connecting AtomClay frontend to Agentom server")

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR / "agentom" / "agentom" / "workspace"
INPUTS_DIR = WORKSPACE_DIR / "inputs"
LOGS_DIR = WORKSPACE_DIR / "logs"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENTOM_BASE_URL = os.getenv("AGENTOM_BASE_URL", "http://localhost:8000")
APP_NAME = "agentom"


def ensure_workspace_dirs():
    for dir_path in [INPUTS_DIR, LOGS_DIR, OUTPUTS_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)


def persist_structure_file(structure: dict):
    if not structure:
        return None

    content = structure.get("content")
    if not content:
        return None

    atom_count = structure.get("atomCount")
    try:
        if atom_count is not None and int(atom_count) <= 0:
            return None
    except Exception:
        # If atomCount is not convertible, continue best-effort
        pass

    ensure_workspace_dirs()
    file_name = structure.get("fileName") or "structure.vasp"
    safe_name = Path(file_name).name
    target_path = INPUTS_DIR / safe_name

    try:
        target_path.write_text(content, encoding="utf-8")
        logger.info("Saved structure to %s (atoms=%s)", target_path, atom_count)
        return target_path
    except Exception as exc:
        logger.exception("Failed to persist structure file")
        raise HTTPException(status_code=500, detail=f"Failed to save structure: {exc}")


def get_final_structure_file():
    """Find the most recently modified structure file in the workspace directory and its outputs subfolder."""
    ensure_workspace_dirs()
    structure_extensions = ['*.cif', '*.poscar', '*.extxyz', '*.vasp', '*.xyz', '*.POSCAR', '*.pdb']
    candidates = []
    for ext in structure_extensions:
        candidates.extend(glob.glob(str(WORKSPACE_DIR / ext)))
        candidates.extend(glob.glob(str(OUTPUTS_DIR / ext)))
    logger.info(f"Found {len(candidates)} structure files: {[str(c) for c in candidates]}")
    if not candidates:
        return None
    # Get the most recent file
    latest_file = max(candidates, key=os.path.getmtime)
    logger.info(f"Selected latest: {latest_file}")
    return Path(latest_file)

class CreateSessionRequest(BaseModel):
    pass  # No body needed for creation

class CreateSessionResponse(BaseModel):
    user_id: str
    session_id: str

class SendMessageRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

class SendMessageResponse(BaseModel):
    response: str  # Or whatever the response is

@app.post("/run")
async def run_agent(request: dict):
    structure_payload = request.pop("structure", None)
    if structure_payload:
        logger.info("Received structure payload keys=%s", list(structure_payload.keys()))
    else:
        logger.info("No structure payload in request")
    # Extract userId and sessionId from request
    user_id = request.get("userId")
    session_id = request.get("sessionId")
    if not user_id or not session_id:
        raise HTTPException(status_code=400, detail="userId and sessionId are required")

    if structure_payload:
        persist_structure_file(structure_payload)

    # First, create the session if not exists
    session_url = f"{AGENTOM_BASE_URL}/apps/{APP_NAME}/users/{user_id}/sessions/{session_id}"
    try:
        requests.post(session_url, json={}, headers={"Content-Type": "application/json"})
        # Ignore if it already exists or fails, as long as we try
    except:
        pass  # Continue anyway

    # Now forward the /run request to agentom
    url = f"{AGENTOM_BASE_URL}/run"
    
    async def stream_generator():
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("POST", url, json=request, headers={"Content-Type": "application/json"}, timeout=None) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except httpx.HTTPStatusError as e:
                # If we can't raise HTTP exception here easily because headers are sent, 
                # we might yield an error message or log it. 
                # But StreamingResponse might have already started.
                # For now, let's just log or yield a specific error structure if possible.
                # But since we are proxying, maybe just let it fail.
                pass
            except Exception as e:
                pass

    try:
        return StreamingResponse(stream_generator(), media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run agent: {str(e)}")

@app.get("/logs/stream")
async def stream_logs():
    ensure_workspace_dirs()
    
    # Find the latest log file
    try:
        list_of_files = glob.glob(str(LOGS_DIR / "*.log"))
        if not list_of_files:
            # If no logs yet, just return empty stream or wait? 
            # Better to return error or wait. Let's return a comment.
            async def empty_gen():
                yield ": No logs found\n\n"
            return StreamingResponse(empty_gen(), media_type="text/event-stream")
            
        latest_file = max(list_of_files, key=os.path.getctime)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding logs: {str(e)}")

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

@app.post("/create_session", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    # Generate unique user_id and session_id
    user_id = f"u_{uuid.uuid4().hex[:6]}"
    session_id = f"s_{uuid.uuid4().hex[:6]}"

    # Call agentom to create session
    url = f"{AGENTOM_BASE_URL}/apps/{APP_NAME}/users/{user_id}/sessions/{session_id}"
    try:
        response = requests.post(url, json={}, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        # Assuming success, return the ids
        return CreateSessionResponse(user_id=user_id, session_id=session_id)
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@app.post("/send_message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    url = f"{AGENTOM_BASE_URL}/apps/{APP_NAME}/users/{request.user_id}/sessions/{request.session_id}"
    try:
        # Assuming sending message is POST to the same URL with message
        data = {"message": request.message}
        response = requests.post(url, json=data, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        # Assuming the response is JSON with the agent's response
        result = response.json()
        return SendMessageResponse(response=result.get("response", str(result)))
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

@app.get("/get_final_structure")
async def get_final_structure():
    """Retrieve the final structure file from the outputs directory."""
    try:
        structure_file = get_final_structure_file()
        if structure_file is None:
            logger.info("No structure file found")
            raise HTTPException(status_code=404, detail="No structure file found")
        
        content = structure_file.read_text(encoding="utf-8")
        file_name = structure_file.name
        file_format = structure_file.suffix.lstrip('.')
        logger.info(f"Returning structure: {file_name}, format: {file_format}")
        return {
            "fileName": file_name,
            "content": content,
            "format": file_format
        }
    except Exception as e:
        logger.error(f"Failed to retrieve structure: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve structure: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)