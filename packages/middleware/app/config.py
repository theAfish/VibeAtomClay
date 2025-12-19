import os
from pathlib import Path

# In middleware/app/config.py
# .parent -> app
# .parent.parent -> middleware
# .parent.parent.parent -> packages
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BASE_DIR.parent

CONFIG_FILE = ROOT_DIR / "config" / "config.json"

WORKSPACE_DIR = BASE_DIR / "agent-server" / "agentom" / "workspace"
INPUTS_DIR = WORKSPACE_DIR / "inputs"
LOGS_DIR = WORKSPACE_DIR / "logs"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"
TEMP_DIR = WORKSPACE_DIR / "tmp"

AGENTOM_BASE_URL = os.getenv("AGENTOM_BASE_URL", "http://localhost:8000")
APP_NAME = "agentom"
