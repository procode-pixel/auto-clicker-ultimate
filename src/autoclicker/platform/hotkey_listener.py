"""Global shortcuts. They are active while the app is running, including when minimized.

If the platform refuses a global hook, the failure is logged and in-window shortcuts still work.
"""

from __future__ import annotations

import logging
from typing import Callable

from autoclicker.core.hotkeys import normalize_combo

log = logging.getLogger("autoclicker.hotkeys")


class HotkeyListener:
    def __init__(self):
        self._listener = None
        self._bindings: dict[str, str] = {}

    def restart(self, bindings: dict[str, str], handler: Callable[[str], None]) -> str | None:
        self.stop()
        mapping = {}
        for action, combo in bindings.items():
            if not combo:
                continue
            try:
                normal = normalize_combo(combo)
            except ValueError:
                continue
            mapping[self._to_pynput(normal)] = action
        if not mapping:
            return None
        try:
            from pynput.keyboard import GlobalHotKeys
        except Exception as exc:
            log.warning("Global hotkeys unavailable: %s", exc)
            return str(exc)
        try:
            listener = GlobalHotKeys({combo: (lambda action=action: handler(action)) for combo, action in mapping.items()})
            listener.start()
        except Exception as exc:
            log.warning("Could not start global hotkeys: %s", exc)
            return str(exc)
        self._listener = listener
        self._bindings = bindings
        return None

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                log.exception("Failed to stop hotkey listener")

    @staticmethod
    def _to_pynput(combo: str) -> str:
        parts = combo.split("+")
        converted = []
        for part in parts:
            if part in {"ctrl", "alt", "shift"}:
                converted.append(f"<{part}>")
            elif part == "win":
                converted.append("<cmd>")
            elif len(part) > 1:
                converted.append(f"<{part}>")
            else:
                converted.append(part)
        return "+".join(converted)
