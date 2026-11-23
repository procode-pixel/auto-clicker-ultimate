"""Filesystem locations for settings, logs, and templates."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    if sys.platform == "win32":
        root = os.environ.get("APPDATA")
        base = Path(root) if root else Path.home() / "AppData" / "Roaming"
        path = base / "AutoClickerUltimate"
    else:
        path = Path.home() / ".local" / "share" / "AutoClickerUltimate"
    path.mkdir(parents=True, exist_ok=True)
    (path / "templates").mkdir(exist_ok=True)
    (path / "exports").mkdir(exist_ok=True)
    return path


def db_path() -> Path:
    return app_data_dir() / "autoclicker.db"


def log_path() -> Path:
    return app_data_dir() / "autoclicker.log"
