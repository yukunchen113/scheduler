import json
import os
from pathlib import Path

from plex.config import (
    get_calendar_email,
    get_config_dir,
    get_config_file,
    load_config,
    save_config,
)
from plex.setup import scaffold_workspace


def test_load_and_save_config(tmp_path, monkeypatch):
    monkeypatch.setenv("PLEX_CONFIG_DIR", str(tmp_path))

    cfg = load_config()
    assert "email" in cfg["calendar"]
    assert isinstance(cfg["calendar"]["email"], str)

    cfg["calendar"]["email"] = "test_user@example.com"
    cfg["notion"]["api_key"] = "test_key_123"
    saved_file = save_config(cfg)

    assert saved_file.exists()
    reloaded = load_config()
    assert reloaded["calendar"]["email"] == "test_user@example.com"
    assert reloaded["notion"]["api_key"] == "test_key_123"


def test_scaffold_workspace(tmp_path):
    scaffold_workspace(str(tmp_path))

    assert (tmp_path / "routines").is_dir()
    assert (tmp_path / "daily").is_dir()
    assert (tmp_path / "weekly").is_dir()
    assert (tmp_path / "routines" / "daily.txt").exists()
    assert (tmp_path / "routines" / "school.txt").exists()
