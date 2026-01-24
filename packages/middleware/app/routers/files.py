from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
import logging
import json
from datetime import datetime
from ..services import (
    get_final_structure_file, 
    save_imported_file, 
    get_exported_file,
    list_session_files,
    get_last_session_id,
    set_last_session_id
)
from ..config import get_session_dirs

router = APIRouter()
logger = logging.getLogger(__name__)

_last_structure_info = None

class FileImportRequest(BaseModel):
    content: str
    filename: str
    sessionId: str
    userId: Optional[str] = None
    format: Optional[str] = None
    isExport: Optional[bool] = False

class FileExportRequest(BaseModel):
    filename: str
    sessionId: str
    userId: Optional[str] = None

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

@router.post("/import")
async def import_file(request: FileImportRequest):
    """
    Import a file into the session's files directory.
    If it's a readable structure format, also convert to extxyz.
    Logs the operation to the operation log.
    """
    try:
        session_id = request.sessionId
        if session_id:
            set_last_session_id(session_id)
        
        # Save the file
        result = save_imported_file(
            content=request.content,
            filename=request.filename,
            session_id=session_id,
            file_format=request.format,
            is_export=request.isExport or False
        )
        
        # Log import vs export based on the request flag
        op_type = "export" if request.isExport else "import"

        await _log_file_operation(
            operation_type=op_type,
            session_id=session_id,
            user_id=request.userId,
            filename=request.filename,
            file_format=result.get('format'),
            file_paths=result
        )
        
        return {
            "status": "success",
            "message": f"File imported successfully",
            "files": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to import file")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@router.post("/export")
async def export_file(request: FileExportRequest):
    """
    Export a file from the session's files directory.
    Logs the operation to the operation log.
    """
    try:
        session_id = request.sessionId
        if session_id:
            set_last_session_id(session_id)
        
        # Get the file
        result = get_exported_file(session_id, request.filename)
        
        # Log the export operation
        await _log_file_operation(
            operation_type="export",
            session_id=session_id,
            user_id=request.userId,
            filename=request.filename,
            file_path=result['path']
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to export file")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@router.get("/list/{session_id}")
async def list_files(session_id: str):
    """List all files in the session's files directory."""
    try:
        if session_id:
            set_last_session_id(session_id)
        
        files = list_session_files(session_id)
        return {
            "sessionId": session_id,
            "files": files
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list files")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

async def _log_file_operation(
    operation_type: str,
    session_id: str,
    user_id: Optional[str],
    filename: str,
    file_format: Optional[str] = None,
    file_paths: Optional[dict] = None,
    file_path: Optional[str] = None
):
    """Helper to log file operations to the operation log."""
    try:
        from ..config import get_session_dirs
        import os
        
        logs_dir = get_session_dirs(session_id)["logs"]
        os.makedirs(logs_dir, exist_ok=True)
        
        date_prefix = datetime.utcnow().strftime("%Y%m%d")
        log_file = os.path.join(logs_dir, f"operations_{date_prefix}_{session_id}.log")
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": f"file_{operation_type}",
            "metadata": {
                "sessionId": session_id,
                "filename": filename,
                "operationType": operation_type
            }
        }
        
        if user_id:
            log_entry["metadata"]["userId"] = user_id
        if file_format:
            log_entry["metadata"]["format"] = file_format
        if file_paths:
            log_entry["metadata"]["filePaths"] = file_paths
        if file_path:
            log_entry["metadata"]["filePath"] = file_path
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
        logger.info(f"Logged {operation_type} operation for {filename}")
        
    except Exception as e:
        logger.warning(f"Failed to log file operation: {e}")
