"""Process entry. Builds the window only after logging and storage are ready."""

from __future__ import annotations

import sys
from pathlib import Path

from autoclicker.controller import open_controller
from autoclicker.logging_setup import configure_logging
from autoclicker.paths import app_data_dir


def run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    configure_logging()
    if "--self-check" in argv:
        return _self_check()
    from PySide6.QtWidgets import QApplication

    from autoclicker.ui.main_window import MainWindow

    app = QApplication(argv)
    app.setApplicationName("Auto Clicker Ultimate")
    app.setOrganizationName("AutoClickerUltimate")
    data = app_data_dir()
    icon = _icon_path()
    controller = open_controller(data)
    window = MainWindow(controller, str(icon) if icon else None)
    if controller.db.get_setting("start_minimized") == "1" and window.tray is not None:
        window.hide()
    else:
        window.show()
    code = app.exec()
    try:
        controller.shutdown()
    except Exception:
        pass
    return int(code)


def _icon_path() -> Path | None:
    candidates = [
        Path(__file__).resolve().parents[2] / "assets" / "icon.png",
        Path(getattr(sys, "_MEIPASS", "")) / "assets" / "icon.png",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _self_check() -> int:
    from autoclicker.core.models import SafetyPolicy
    from autoclicker.core.presets import builtin_profiles
    from autoclicker.core.safety import validate_job

    policy = SafetyPolicy()
    for profile in builtin_profiles():
        errors = [err for err in validate_job(profile.job, policy) if "confirmation" not in err]
        if errors:
            print("SELF-CHECK FAILED", profile.name, errors)
            return 1
    print("SELF-CHECK OK")
    return 0
