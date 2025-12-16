import json
import logging
import shutil
import glob
import os
from datetime import datetime
from pathlib import Path
from fastapi import HTTPException
from .config import CONFIG_FILE, WORKSPACE_DIR, INPUTS_DIR, LOGS_DIR, OUTPUTS_DIR, TEMP_DIR, BASE_DIR, ROOT_DIR

logger = logging.getLogger(__name__)

# Track the last session ID to detect new sessions
_last_seen_session_id = None

def ensure_workspace_dirs():
    for dir_path in [INPUTS_DIR, LOGS_DIR, OUTPUTS_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)

def archive_workspace():
    """Archives outputs from the workspace to the archive directory."""
    logger.info("Archiving workspace outputs...")
    
    # Determine archive directory
    archive_root = ROOT_DIR / "outputs_archive"
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                if "OUTPUT_ARCHIVE_DIR" in config:
                    p = Path(config["OUTPUT_ARCHIVE_DIR"])
                    if p.is_absolute():
                        archive_root = p
                    else:
                        archive_root = ROOT_DIR / p
        except Exception:
            pass
            
    # Create timestamped folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = archive_root / timestamp
    archive_path.mkdir(parents=True, exist_ok=True)
    
    # Transfer outputs to archive
    if OUTPUTS_DIR.exists():
        for item in OUTPUTS_DIR.iterdir():
            try:
                dest = archive_path / item.name
                if item.is_file():
                    shutil.move(str(item), str(dest))
                elif item.is_dir():
                    shutil.move(str(item), str(dest))
                logger.info(f"Archived {item.name} to {dest}")
            except Exception as e:
                logger.error(f"Failed to move {item} to archive: {e}")
    logger.info(f"Transferred outputs to target directory: {archive_path}")

def cleanup_workspace():
    logger.info("Cleaning up workspace...")
    
    # 1. Archive existing outputs
    archive_workspace()
                
    # 2. Clear Inputs, Outputs, Temp
    dirs_to_clear = [INPUTS_DIR, OUTPUTS_DIR, TEMP_DIR]
    for d in dirs_to_clear:
        if d.exists():
            for item in d.iterdir():
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as e:
                    logger.error(f"Failed to delete {item} in {d}: {e}")
            logger.info(f"Cleared directory: {d}")
                    
    # 3. Clear Workspace Root Files (excluding dirs)
    if WORKSPACE_DIR.exists():
        for item in WORKSPACE_DIR.iterdir():
            if item.is_file() or item.is_symlink():
                 try:
                    item.unlink()
                 except Exception as e:
                    logger.error(f"Failed to delete {item} in workspace root: {e}")
        logger.info(f"Cleared workspace directory: {WORKSPACE_DIR}")
    
    logger.info("Workspace cleanup complete.")

def check_new_session(session_id: str):
    global _last_seen_session_id
    if session_id != _last_seen_session_id:
        logger.info(f"New session detected: {session_id} (old: {_last_seen_session_id})")
        cleanup_workspace()
        _last_seen_session_id = session_id

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
    file_name = structure.get("fileName") or "structure.poscar"
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
