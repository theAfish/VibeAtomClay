import os
import json
from pathlib import Path
from datetime import datetime

# In middleware/app/config.py
# .parent -> app
# .parent.parent -> middleware
# .parent.parent.parent -> packages
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # .../packages
ROOT_DIR = BASE_DIR.parent  # repo root

CONFIG_FILE = ROOT_DIR / "config" / "config.json"


def _load_config():
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _resolve_path(p: str) -> Path:
    path_obj = Path(p)
    return path_obj if path_obj.is_absolute() else (ROOT_DIR / path_obj)


CONFIG = _load_config()

# Workspace root can be configured via config.json WORKSPACE_ROOT; fallback to legacy path
_workspace_root = CONFIG.get("WORKSPACE_ROOT", "packages/agent-server/agentom/workspace")
WORKSPACE_DIR = _resolve_path(_workspace_root)

AGENTOM_BASE_URL = os.getenv("AGENTOM_BASE_URL", "http://localhost:8000")
APP_NAME = "agentom"

def get_session_workspace(session_id: str) -> Path:
    """Get or create the session-specific workspace directory, ensuring root exists."""
    try:
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If mkdir fails due to race, continue; subsequent ops may succeed
        pass

    # List subfolders in WORKSPACE_DIR that contain session_id
    try:
        for item in WORKSPACE_DIR.iterdir():
            if item.is_dir() and session_id in item.name:
                return item
    except FileNotFoundError:
        # Root may have been removed concurrently; recreate
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    # If not found, create a new one with datetime
    dt = datetime.now()
    session_folder = f"{dt.strftime('%Y%m%d_%H%M%S')}-{session_id}"
    session_path = WORKSPACE_DIR / session_folder
    session_path.mkdir(parents=True, exist_ok=True)
    return session_path

def get_session_dirs(session_id: str):
    """Get session-specific directories, ensuring base exists."""
    session_workspace = get_session_workspace(session_id)
    logs_dir = WORKSPACE_DIR / "logs"
    # Ensure the logs directory exists regardless of session state
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return {
        'workspace': session_workspace,
        'inputs': session_workspace / "inputs",
        'logs': logs_dir,
        'outputs': session_workspace / "outputs",
        'temp': session_workspace / "tmp"
    }
