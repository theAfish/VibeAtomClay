from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import requests
import httpx
import uuid
import logging
from ..models import CreateSessionRequest, CreateSessionResponse, SendMessageRequest, SendMessageResponse
from ..services import check_new_session, persist_structure_file, cleanup_workspace
from ..config import AGENTOM_BASE_URL, APP_NAME

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/run")
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

    # Detect new session and cleanup
    check_new_session(session_id)

    if structure_payload:
        persist_structure_file(structure_payload)

    # First, create the session if not exists
    session_url = f"{AGENTOM_BASE_URL}/apps/{APP_NAME}/users/{user_id}/sessions/{session_id}"
    try:
        async with httpx.AsyncClient() as client:
            await client.post(session_url, json={}, headers={"Content-Type": "application/json"})
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

@router.post("/create_session", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    # Cleanup workspace before starting new session
    cleanup_workspace()

    # Generate unique user_id and session_id
    user_id = f"u_{uuid.uuid4().hex[:6]}"
    session_id = f"s_{uuid.uuid4().hex[:6]}"

    # Call agentom to create session
    url = f"{AGENTOM_BASE_URL}/apps/{APP_NAME}/users/{user_id}/sessions/{session_id}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={}, headers={"Content-Type": "application/json"})
            response.raise_for_status()
        # Assuming success, return the ids
        return CreateSessionResponse(user_id=user_id, session_id=session_id)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@router.post("/send_message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    url = f"{AGENTOM_BASE_URL}/apps/{APP_NAME}/users/{request.user_id}/sessions/{request.session_id}"
    try:
        # Assuming sending message is POST to the same URL with message
        data = {"message": request.message}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            # Assuming the response is JSON with the agent's response
            result = response.json()
        return SendMessageResponse(response=result.get("response", str(result)))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
