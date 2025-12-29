import json
import logging
import shutil
import glob
import os
from datetime import datetime
from pathlib import Path
from fastapi import HTTPException
from .config import CONFIG_FILE, WORKSPACE_DIR, get_session_dirs, ROOT_DIR

logger = logging.getLogger(__name__)

# Track the last session ID
_last_session_id = None

def set_last_session_id(session_id: str):
    global _last_session_id
    _last_session_id = session_id

def get_last_session_id() -> str:
    return _last_session_id

def ensure_workspace_dirs(session_id: str):
    dirs = get_session_dirs(session_id)
    for dir_path in [dirs['inputs'], dirs['logs'], dirs['outputs']]:
        dir_path.mkdir(parents=True, exist_ok=True)

def persist_structure_file(structure: dict, session_id: str):
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

    ensure_workspace_dirs(session_id)
    dirs = get_session_dirs(session_id)
    file_name = structure.get("fileName") or "structure.poscar"
    safe_name = Path(file_name).name
    target_path = dirs['inputs'] / safe_name

    try:
        target_path.write_text(content, encoding="utf-8")
        logger.info("Saved structure to %s (atoms=%s)", target_path, atom_count)
        return target_path
    except Exception as exc:
        logger.exception("Failed to persist structure file")
        raise HTTPException(status_code=500, detail=f"Failed to save structure: {exc}")

def get_final_structure_file():
    """Find the most recently modified structure file in the session's workspace and outputs subfolder."""
    session_id = get_last_session_id()
    if not session_id:
        logger.warning("No session ID available for getting final structure")
        return None
    ensure_workspace_dirs(session_id)
    dirs = get_session_dirs(session_id)
    structure_extensions = ['*.cif', '*.poscar', '*.extxyz', '*.vasp', '*.xyz', '*.POSCAR', '*.pdb']
    candidates = []
    for ext in structure_extensions:
        candidates.extend(glob.glob(str(dirs['workspace'] / ext)))
        candidates.extend(glob.glob(str(dirs['outputs'] / ext)))
    logger.info(f"Found {len(candidates)} structure files: {[str(c) for c in candidates]}")
    if not candidates:
        return None
    # Get the most recent file
    latest_file = max(candidates, key=os.path.getmtime)
    logger.info(f"Selected latest: {latest_file}")
    return Path(latest_file)
