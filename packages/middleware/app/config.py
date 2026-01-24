import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# In middleware/app/config.py
# .parent -> app
# .parent.parent -> middleware
# .parent.parent.parent -> packages
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # .../packages
ROOT_DIR = BASE_DIR.parent  # repo root

CONFIG_FILE = ROOT_DIR / "config" / "config.json"
ENV_FILE = ROOT_DIR / "config" / ".env"
TRACKED_ENV_KEYS = ["OPENAI_API_KEY", "OPENAI_API_BASE", "MP_API_KEY", "AGENTOM_BASE_URL"]


def _file_mtime(path: Path) -> Optional[float]:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return None


def _load_config() -> Dict:
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _read_env_file() -> Dict[str, str]:
    env_data: Dict[str, str] = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for raw_line in f.readlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env_data[key.strip()] = value.strip()
    return env_data


def _resolve_path(p: str) -> Path:
    path_obj = Path(p)
    return path_obj if path_obj.is_absolute() else (ROOT_DIR / path_obj)


CONFIG = _load_config()
_config_mtime = _file_mtime(CONFIG_FILE)
_env_mtime = _file_mtime(ENV_FILE)

# Workspace root can be configured via config.json WORKSPACE_ROOT; fallback to legacy path
_workspace_root = CONFIG.get("WORKSPACE_ROOT", "packages/agent-server/agentom/workspace")
WORKSPACE_DIR = _resolve_path(_workspace_root)

AGENTOM_BASE_URL = os.getenv("AGENTOM_BASE_URL", "http://localhost:8000")
APP_NAME = "agentom"


def _reload_if_stale():
    """Reload config/env into module-level values when files change."""
    global CONFIG, WORKSPACE_DIR, _workspace_root, _config_mtime, _env_mtime, AGENTOM_BASE_URL

    config_mtime = _file_mtime(CONFIG_FILE)
    env_mtime = _file_mtime(ENV_FILE)

    if config_mtime != _config_mtime:
        CONFIG = _load_config()
        _workspace_root = CONFIG.get("WORKSPACE_ROOT", "packages/agent-server/agentom/workspace")
        WORKSPACE_DIR = _resolve_path(_workspace_root)
        _config_mtime = config_mtime

    if env_mtime != _env_mtime:
        env_data = _read_env_file()
        for key, value in env_data.items():
            os.environ[key] = value
        for tracked in TRACKED_ENV_KEYS:
            if tracked not in env_data and tracked in os.environ:
                os.environ.pop(tracked, None)
        _env_mtime = env_mtime

    # Always refresh derived URL from current environment
    AGENTOM_BASE_URL = os.getenv("AGENTOM_BASE_URL", "http://localhost:8000")

def get_session_workspace(session_id: str) -> Path:
    """Get or create the session-specific workspace directory, ensuring root exists."""
    _reload_if_stale()
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
    _reload_if_stale()
    session_workspace = get_session_workspace(session_id)
    logs_dir = WORKSPACE_DIR / "logs"
    files_dir = WORKSPACE_DIR / "files" / session_id
    # Ensure the logs and files directories exist regardless of session state
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        files_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return {
        'workspace': session_workspace,
        'inputs': session_workspace / "inputs",
        'logs': logs_dir,
        'outputs': session_workspace / "outputs",
        'temp': session_workspace / "tmp",
        'files': files_dir
    }


def get_agentom_base_url() -> str:
    _reload_if_stale()
    return AGENTOM_BASE_URL


def get_app_name() -> str:
    return APP_NAME
