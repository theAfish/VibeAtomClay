import os
from pathlib import Path
from datetime import datetime

# In middleware/app/config.py
# .parent -> app
# .parent.parent -> middleware
# .parent.parent.parent -> packages
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BASE_DIR.parent

CONFIG_FILE = ROOT_DIR / "config" / "config.json"

WORKSPACE_DIR = BASE_DIR / "agent-server" / "agentom" / "workspace"

AGENTOM_BASE_URL = os.getenv("AGENTOM_BASE_URL", "http://localhost:8000")
APP_NAME = "agentom"

def get_session_workspace(session_id: str) -> Path:
    """Get the session-specific workspace directory."""
    # List subfolders in WORKSPACE_DIR that contain session_id
    for item in WORKSPACE_DIR.iterdir():
        if item.is_dir() and session_id in item.name:
            return item
    # If not found, create a new one with datetime
    dt = datetime.now()
    session_folder = f"{dt.strftime('%Y%m%d_%H%M%S')}-{session_id}"
    session_path = WORKSPACE_DIR / session_folder
    session_path.mkdir(parents=True, exist_ok=True)
    return session_path

def get_session_dirs(session_id: str):
    """Get session-specific directories."""
    session_workspace = get_session_workspace(session_id)
    return {
        'workspace': session_workspace,
        'inputs': session_workspace / "inputs",
        'logs': WORKSPACE_DIR / "logs",
        'outputs': session_workspace / "outputs",
        'temp': session_workspace / "tmp"
    }
