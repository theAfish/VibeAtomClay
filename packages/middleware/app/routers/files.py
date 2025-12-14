from fastapi import APIRouter, HTTPException
import logging
from ..services import get_final_structure_file

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/get_final_structure")
async def get_final_structure():
    """Retrieve the final structure file from the outputs directory."""
    try:
        structure_file = get_final_structure_file()
        if structure_file is None:
            logger.info("No structure file found")
            raise HTTPException(status_code=404, detail="No structure file found")
        
        content = structure_file.read_text(encoding="utf-8")
        file_name = structure_file.name
        
        logger.info(f"Returning structure: {file_name}")
        return {
            "fileName": file_name,
            "content": content
        }
    except Exception as e:
        logger.error(f"Failed to retrieve structure: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve structure: {str(e)}")
