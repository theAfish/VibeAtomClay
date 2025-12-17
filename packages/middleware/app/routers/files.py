from fastapi import APIRouter, HTTPException
import logging
from ..services import get_final_structure_file

router = APIRouter()
logger = logging.getLogger(__name__)

_last_structure_info = None

@router.get("/get_final_structure")
async def get_final_structure():
    """Retrieve the final structure file from the outputs directory."""
    global _last_structure_info
    try:
        structure_file = get_final_structure_file()
        if structure_file is None:
            logger.info("No structure file found")
            return None
        
        # Check if the structure is new
        current_mtime = structure_file.stat().st_mtime
        current_path = str(structure_file)
        
        logger.info(f"Checking structure: {current_path} (mtime={current_mtime})")
        
        if _last_structure_info == (current_path, current_mtime):
            logger.info("No new structure generated (matches last memory).")
            return None

        _last_structure_info = (current_path, current_mtime)
        
        content = structure_file.read_text(encoding="utf-8")
        file_name = structure_file.name
        
        logger.info(f"Returning structure: {file_name}")
        return {
            "fileName": file_name,
            "content": content
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve structure: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve structure: {str(e)}")
