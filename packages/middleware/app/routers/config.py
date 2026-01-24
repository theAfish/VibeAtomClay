from fastapi import APIRouter, HTTPException
import json
import logging
import os
from typing import Dict

from ..config import CONFIG_FILE, ROOT_DIR, _reload_if_stale

router = APIRouter()
logger = logging.getLogger(__name__)

# Shared config/env file locations
ENV_FILE = ROOT_DIR / "config" / ".env"

# Required configuration keys for the system to function properly
REQUIRED_CONFIG_KEYS = [
    "AGENTOM_MODEL",
    "VISION_MODEL",
    "WIKI_MODEL",
    "STRUCTURE_MODEL",
    "MP_MODEL"
]

# Required environment variables for critical features
REQUIRED_ENV_KEYS = [
    "OPENAI_API_KEY",
    "OPENAI_API_BASE",
    "MP_API_KEY"
]


def _read_env_file() -> Dict[str, str]:
    """Read key/value pairs from the shared .env file."""
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


def _write_env_file(env_data: Dict[str, str]) -> None:
    """Persist env data back to disk."""
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={v}" for k, v in env_data.items()]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

@router.post("/set_config")
async def set_config(config: dict):
    """Set the configuration for the agent server."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        _reload_if_stale()
        return {"message": "Config updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.get("/config")
async def get_config():
    """Return current config.json contents (if present)."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@router.get("/env")
async def get_env():
    """Return the known API-related env keys with masked values."""
    env_data = _read_env_file()
    tracked_keys = ["OPENAI_API_KEY", "OPENAI_API_BASE", "MP_API_KEY"]
    payload = {}
    for key in tracked_keys:
        raw = env_data.get(key, "")
        has_value = bool(raw)
        masked = "*" * min(len(raw), 6) if has_value else ""
        payload[key] = {"hasValue": has_value, "masked": masked}
    return payload


@router.post("/set_env")
async def set_env(env_updates: dict):
    """Merge updates into the shared .env file.

    - Omitted keys remain unchanged
    - Empty string clears the value
    """
    try:
        env_data = _read_env_file()
        for key, value in env_updates.items():
            if value is None:
                continue
            if isinstance(value, str) and value == "":
                env_data.pop(key, None)
            else:
                env_data[key] = value

        _write_env_file(env_data)
        _reload_if_stale()
        return {"message": "Env updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update env: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update env: {str(e)}")


@router.get("/validate")
async def validate_config():
    """Validate that config and .env are properly set.
    
    Returns a status report with missing required keys and warnings.
    """
    config_data = {}
    env_data = _read_env_file()
    env_effective = {}
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read config file: {str(e)}")
    
    # Check for missing required config keys
    missing_config_keys = []
    for key in REQUIRED_CONFIG_KEYS:
        if key not in config_data or not config_data[key]:
            missing_config_keys.append(key)
    
    # Consider both real environment variables and .env entries
    for key in REQUIRED_ENV_KEYS:
        env_effective[key] = os.getenv(key) or env_data.get(key, "")

    # Check for missing required env keys
    missing_env_keys = [key for key, value in env_effective.items() if not value]
    
    # Determine overall status
    is_properly_set = len(missing_config_keys) == 0 and len(missing_env_keys) == 0
    
    return {
        "is_properly_set": is_properly_set,
        "missing_config_keys": missing_config_keys,
        "missing_env_keys": missing_env_keys,
        "warnings": [
            f"Missing config key: {key}" for key in missing_config_keys
        ] + [
            f"Missing environment variable: {key}" for key in missing_env_keys
        ]
    }
