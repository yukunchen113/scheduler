"""
Plex Configuration & Secrets Management

Stores user configuration and secrets in a standard user config location:
  ~/.config/plex/config.json (or $XDG_CONFIG_HOME/plex/config.json)

Falls back gracefully to legacy ~/.credentials/ or plex.secrets if present,
and provides sensible offline defaults when cloud services are unconfigured.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional


def get_config_dir() -> Path:
    config_dir_str = os.environ.get(
        "PLEX_CONFIG_DIR",
        os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "plex"
        ),
    )
    config_dir = Path(config_dir_str)
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    return get_config_dir() / "config.json"


def get_default_config() -> dict[str, Any]:
    config_dir = str(get_config_dir())
    return {
        "calendar": {
            "enabled": False,
            "email": "primary",
            "credentials_file": os.path.join(config_dir, "credentials.json"),
            "token_json": os.path.join(config_dir, "token.json"),
            "token_pickle": os.path.join(config_dir, "token.pickle"),
        },
        "notion": {
            "enabled": False,
            "api_key": None,
            "page_name": "Schedule",
        },
        "preferences": {
            "wake_time": "07:30",
            "bed_time": "23:30",
            "default_routine": "school",
        },
        "locations": {
            "@Home": "742 Evergreen Terr, Springfield",
            "@Office": "500 Corporate Way, New York, NY",
            "@Campus": "100 University Ave, New York, NY",
            "@Gym": "45 Fitness Blvd, New York, NY",
            "@Cafe": "88 Artisan Way, New York, NY",
        },
        "routes": {
            "api_key": None,
            "default_mode": "drive",
            "buffer_multiplier": 1.25,
        },
    }


def load_config() -> dict[str, Any]:
    """Loads configuration from config.json, merging with defaults and legacy fallbacks."""
    config = get_default_config()
    cfg_file = get_config_file()

    if cfg_file.exists():
        try:
            with open(cfg_file, "r") as f:
                user_cfg = json.load(f)
                for section, vals in user_cfg.items():
                    if isinstance(vals, dict) and section in config:
                        config[section].update(vals)
                    else:
                        config[section] = vals
        except Exception as err:
            print(f"Warning: Failed to parse {cfg_file}: {err}")

    # Fallback to legacy secrets if available
    try:
        from plex.secrets import email as legacy_email  # type: ignore

        if config["calendar"]["email"] == "primary" and legacy_email:
            config["calendar"]["email"] = legacy_email
    except (ImportError, ModuleNotFoundError):
        pass

    # Fallback to legacy ~/.credentials/ if local config tokens don't exist
    legacy_cred_dir = os.path.expanduser("~/.credentials")
    if not os.path.exists(config["calendar"]["credentials_file"]):
        legacy_creds = os.path.join(legacy_cred_dir, "credentials.json")
        if os.path.exists(legacy_creds):
            config["calendar"]["credentials_file"] = legacy_creds

    if not os.path.exists(config["calendar"]["token_json"]):
        legacy_token_json = os.path.join(legacy_cred_dir, "token.json")
        if os.path.exists(legacy_token_json):
            config["calendar"]["token_json"] = legacy_token_json

    if not os.path.exists(config["calendar"]["token_pickle"]):
        legacy_token_pickle = os.path.join(legacy_cred_dir, "token.pickle")
        if os.path.exists(legacy_token_pickle):
            config["calendar"]["token_pickle"] = legacy_token_pickle

    # Check legacy notion key
    legacy_notion_key = os.path.join(legacy_cred_dir, "notion-api-key")
    if not config["notion"]["api_key"] and os.path.exists(legacy_notion_key):
        try:
            with open(legacy_notion_key, "r") as f:
                config["notion"]["api_key"] = f.read().strip()
                config["notion"]["enabled"] = True
        except Exception:
            pass

    return config


def save_config(config_data: dict[str, Any]) -> Path:
    """Saves configuration to config.json with restricted 0600 permissions."""
    cfg_file = get_config_file()
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_file, "w") as f:
        json.dump(config_data, f, indent=2)

    # Secure file permissions (owner read/write only)
    try:
        os.chmod(cfg_file, 0o600)
    except Exception:
        pass

    return cfg_file


def get_calendar_email() -> str:
    cfg = load_config()
    return cfg.get("calendar", {}).get("email", "primary")


def get_credentials_path() -> str:
    cfg = load_config()
    return cfg.get("calendar", {}).get(
        "credentials_file", str(get_config_dir() / "credentials.json")
    )


def get_token_json_path() -> str:
    cfg = load_config()
    return cfg.get("calendar", {}).get(
        "token_json", str(get_config_dir() / "token.json")
    )


def get_token_pickle_path() -> str:
    cfg = load_config()
    return cfg.get("calendar", {}).get(
        "token_pickle", str(get_config_dir() / "token.pickle")
    )


def get_notion_api_key() -> Optional[str]:
    cfg = load_config()
    return cfg.get("notion", {}).get("api_key")


def get_locations() -> dict[str, str]:
    cfg = load_config()
    return cfg.get("locations", {})


def save_location(name: str, address: str) -> None:
    cfg = load_config()
    if "locations" not in cfg:
        cfg["locations"] = {}
    if not name.startswith("@"):
        name = f"@{name}"
    cfg["locations"][name] = address
    save_config(cfg)


def get_routes_config() -> dict[str, Any]:
    cfg = load_config()
    routes_cfg = cfg.get("routes", {})
    # Check env var for API key override
    env_key = os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get(
        "GOOGLE_ROUTES_API_KEY"
    )
    if env_key and not routes_cfg.get("api_key"):
        routes_cfg["api_key"] = env_key
    return routes_cfg
