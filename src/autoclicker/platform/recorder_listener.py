"""Optional pynput capture for the macro recorder. Recording is visible and user-started."""

from __future__ import annotations

import logging

log = logging.getLogger("autoclicker.recorder")


class RecorderListener:
    def __init__(self, recorder):
        self.recorder = recorder
        self._mouse = None
        self._keyboard = None

    def start(self) -> str | None:
        self.stop()
        try:
            from pynput import keyboard, mouse
        except Exception as exc:
            return f"Input monitoring is unavailable: {exc}"
        try:
            self._mouse = mouse.Listener(on_move=self._move, on_click=self._click)
            self._keyboard = keyboard.Listener(on_press=self._press, on_release=self._release)
            self._mouse.start()
            self._keyboard.start()
        except Exception as exc:
            log.warning("Recorder listener failed: %s", exc)
            self.stop()
            return str(exc)
        return None

    def stop(self) -> None:
        for listener in (self._mouse, self._keyboard):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    log.exception("Failed to stop recorder listener")
        self._mouse = None
        self._keyboard = None

    def _move(self, x, y):
        self.recorder.add("move", x=int(x), y=int(y))

    def _click(self, x, y, button, pressed):
        name = str(button).split(".")[-1]
        self.recorder.add(
            "click",
            x=int(x),
            y=int(y),
            button=name if name in {"left", "right", "middle"} else "left",
            action="press" if pressed else "release",
        )

    def _name(self, key) -> str:
        value = getattr(key, "char", None)
        if value:
            return value.lower()
        return str(key).replace("Key.", "")

    def _press(self, key):
        self.recorder.add("key", key=self._name(key), action="press")

    def _release(self, key):
        self.recorder.add("key", key=self._name(key), action="release")
