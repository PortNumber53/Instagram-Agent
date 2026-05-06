"""Configuration loader for Instagram-Agent.

Loads settings from multiple sources in order of priority:
1. Environment variables (highest priority)
2. .env file in the project directory
3. ~/.config/instagram-agent/config.ini with [default] section (lowest priority)
"""

import configparser
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file if present (from current working directory)
load_dotenv()


CONFIG_DIR = Path.home() / ".config" / "instagram-agent"
CONFIG_FILE = CONFIG_DIR / "config.ini"


def _load_config_ini() -> configparser.ConfigParser:
    """Load the config.ini file from ~/.config/instagram-agent/"""
    parser = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        parser.read(CONFIG_FILE)
    return parser


def _get_from_config_ini(key: str) -> Optional[str]:
    """Get a value from config.ini [default] section."""
    parser = _load_config_ini()
    return parser.get("default", key, fallback=None)


def get_nvidia_api_key() -> str:
    """Get the NVIDIA API key from env, .env, or config.ini.

    Priority:
      1. NVIDIA_API_KEY environment variable
      2. .env file (already loaded by dotenv at import time)
      3. ~/.config/instagram-agent/config.ini [default] section

    Raises:
        SystemExit: If no API key is found in any source.
    """
    # 1. Check environment (includes .env loaded by dotenv)
    key = os.environ.get("NVIDIA_API_KEY")
    if key:
        return key

    # 2. Check config.ini
    key = _get_from_config_ini("NVIDIA_API_KEY")
    if key:
        return key

    # Not found anywhere
    print(
        "ERROR: NVIDIA_API_KEY not found.\n"
        "Set it via one of:\n"
        "  1. Export: export NVIDIA_API_KEY=nvapi-xxxxx\n"
        f"  2. .env file in project root\n"
        f"  3. config.ini at {CONFIG_FILE} with [default] section\n"
    )
    raise SystemExit(1)


def get_config_dir() -> Path:
    """Return the config directory path, creating it if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def get(key: str, default: Optional[str] = None) -> Optional[str]:
    """Generic config getter — checks env vars then config.ini."""
    value = os.environ.get(key)
    if value:
        return value
    value = _get_from_config_ini(key)
    if value:
        return value
    return default


# ── Instagram / Facebook OAuth config ──────────────────────────────────

def get_fb_app_id() -> Optional[str]:
    """Get the Facebook App ID from env or config.ini."""
    return get("FB_APP_ID")


def get_fb_app_secret() -> Optional[str]:
    """Get the Facebook App Secret from env or config.ini."""
    return get("FB_APP_SECRET")


def get_ig_access_token() -> Optional[str]:
    """Get the stored Instagram long-lived access token."""
    return get("IG_ACCESS_TOKEN")


def get_ig_account_id() -> Optional[str]:
    """Get the Instagram Business Account ID."""
    return get("IG_ACCOUNT_ID")


def save_token_to_config(key: str, value: str) -> None:
    """Persist a key=value pair into ~/.config/instagram-agent/config.ini.

    Creates the file and [default] section if they don't exist.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    parser = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        parser.read(CONFIG_FILE)
    if not parser.has_section("default"):
        parser.add_section("default")
    parser.set("default", key, value)
    with open(CONFIG_FILE, "w") as f:
        parser.write(f)
