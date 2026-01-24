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
    for dir_path in [dirs['inputs'], dirs['logs'], dirs['outputs'], dirs['files']]:
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

def save_imported_file(content: str, filename: str, session_id: str, file_format: str = None, is_export: bool = False):
    """Save a file to the session's files directory as ExtXYZ only.
    If is_export=True, adds timestamp to filename.
    Returns the saved file path as a dict with 'extxyz' key.
    """
    ensure_workspace_dirs(session_id)
    dirs = get_session_dirs(session_id)
    files_dir = dirs['files']
    
    # Sanitize filename
    safe_name = Path(filename).name
    base_name = Path(safe_name).stem
    
    # Add timestamp for exports
    if is_export:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{base_name}_{timestamp}"
    
    result = {'extxyz': None, 'format': file_format, 'original_filename': filename}
    
    try:
        # Detect format
        structure_formats = ['cif', 'poscar', 'vasp', 'xyz', 'pdb', 'extxyz']
        detected_format = file_format or _detect_structure_format(filename, content)
        
        if detected_format and detected_format.lower() in structure_formats:
            try:
                from ase.io import read, write
                import tempfile
                
                # Use ASE to read and convert to extxyz
                with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{detected_format}', delete=False, encoding='utf-8') as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                
                try:
                    atoms = read(tmp_path, format=detected_format if detected_format != 'extxyz' else 'xyz')
                    
                    # Save as extxyz only
                    extxyz_name = f"{base_name}.extxyz"
                    extxyz_path = files_dir / extxyz_name
                    write(str(extxyz_path), atoms, format='extxyz')
                    result['extxyz'] = str(extxyz_path)
                    result['format'] = detected_format
                    result['saved_filename'] = extxyz_name
                    logger.info(f"Saved as extxyz: {extxyz_path}")
                finally:
                    os.unlink(tmp_path)
                    
            except Exception as e:
                logger.warning(f"Could not convert to extxyz: {e}")
                raise HTTPException(status_code=400, detail=f"Failed to convert file: {e}")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format. Expected structure file (CIF, POSCAR, XYZ, PDB).")
        
        return result
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save imported file")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

def _detect_structure_format(filename: str, content: str) -> str:
    """Detect structure file format from filename or content."""
    ext = Path(filename).suffix.lower().lstrip('.')
    
    # Map common extensions
    format_map = {
        'cif': 'cif',
        'poscar': 'poscar',
        'vasp': 'vasp',
        'xyz': 'xyz',
        'extxyz': 'extxyz',
        'pdb': 'pdb'
    }
    
    if ext in format_map:
        return format_map[ext]
    
    # Try to detect from content
    if content.strip().startswith('data_'):
        return 'cif'
    elif 'POSCAR' in content[:100] or 'CONTCAR' in content[:100]:
        return 'poscar'
    
    return None

def get_exported_file(session_id: str, filename: str):
    """Retrieve an exported file from the session's files directory."""
    ensure_workspace_dirs(session_id)
    dirs = get_session_dirs(session_id)
    file_path = dirs['files'] / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    try:
        content = file_path.read_text(encoding="utf-8")
        return {
            'filename': filename,
            'content': content,
            'path': str(file_path)
        }
    except Exception as exc:
        logger.exception("Failed to read exported file")
        raise HTTPException(status_code=500, detail=f"Failed to read file: {exc}")

def list_session_files(session_id: str):
    """List all files in the session's files directory."""
    ensure_workspace_dirs(session_id)
    dirs = get_session_dirs(session_id)
    files_dir = dirs['files']
    
    if not files_dir.exists():
        return []
    
    try:
        files = []
        for file_path in files_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    'filename': file_path.name,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'path': str(file_path)
                })
        return sorted(files, key=lambda x: x['modified'], reverse=True)
    except Exception as exc:
        logger.exception("Failed to list session files")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {exc}")
