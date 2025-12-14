from fastapi import APIRouter, HTTPException
import json
import logging
from ..config import CONFIG_FILE

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/set_config")
async def set_config(config: dict):
    """Set the configuration for the agent server."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return {"message": "Config updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")
