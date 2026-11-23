"""Mouse and keyboard backends.

Win32 SendInput is used on Windows. pynput is the fallback. Tests use FakeBackend.
Nothing here hides the cursor, injects into another process, or requests administrator rights.
"""

from __future__ import annotations

import sys
from typing import Protocol


class InputBackend(Protocol):
    def move(self, x: int, y: int) -> None: ...
    def click(self, button: str, count: int = 1, interval_ms: int = 40) -> None: ...
    def mouse_press(self, button: str) -> None: ...
    def mouse_release(self, button: str) -> None: ...
    def cursor(self) -> tuple[int, int]: ...
    def press_key(self, key: str) -> None: ...
    def release_key(self, key: str) -> None: ...
    def tap_key(self, key: str) -> None: ...
    def hotkey(self, keys: list[str]) -> None: ...


class FakeBackend:
    """Records events. Used by tests and by the self-check."""

    def __init__(self, cursor: tuple[int, int] = (10, 10)):
        self.events: list[tuple] = []
        self.pos = cursor

    def move(self, x: int, y: int) -> None:
        self.pos = (int(x), int(y))
        self.events.append(("move", self.pos))

    def click(self, button: str, count: int = 1, interval_ms: int = 40) -> None:
        for _ in range(int(count)):
            self.events.append(("click", button, self.pos))

    def mouse_press(self, button: str) -> None:
        self.events.append(("press", button, self.pos))

    def mouse_release(self, button: str) -> None:
        self.events.append(("release", button, self.pos))

    def cursor(self) -> tuple[int, int]:
        return self.pos

    def press_key(self, key: str) -> None:
        self.events.append(("key_down", key))

    def release_key(self, key: str) -> None:
        self.events.append(("key_up", key))

    def tap_key(self, key: str) -> None:
        self.press_key(key)
        self.release_key(key)

    def hotkey(self, keys: list[str]) -> None:
        for key in keys:
            self.press_key(key)
        for key in reversed(keys):
            self.release_key(key)


class Win32Backend:
    """Native input through SendInput / GetCursorPos. No elevation required."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._user32 = ctypes.windll.user32
        self._wintypes = wintypes
        self._down = {"left": 0x0002, "right": 0x0008, "middle": 0x0020}
        self._up = {"left": 0x0004, "right": 0x0010, "middle": 0x0040}

    def cursor(self) -> tuple[int, int]:
        point = self._wintypes.POINT()
        self._user32.GetCursorPos(self._ctypes.byref(point))
        return int(point.x), int(point.y)

    def move(self, x: int, y: int) -> None:
        self._user32.SetCursorPos(int(x), int(y))

    def mouse_press(self, button: str) -> None:
        self._user32.mouse_event(self._down[button], 0, 0, 0, 0)

    def mouse_release(self, button: str) -> None:
        self._user32.mouse_event(self._up[button], 0, 0, 0, 0)

    def click(self, button: str, count: int = 1, interval_ms: int = 40) -> None:
        import time

        for index in range(int(count)):
            self.mouse_press(button)
            self.mouse_release(button)
            if index + 1 < int(count):
                time.sleep(max(interval_ms, 1) / 1000.0)

    def press_key(self, key: str) -> None:
        vk = _vk(key)
        self._user32.keybd_event(vk, 0, 0, 0)

    def release_key(self, key: str) -> None:
        vk = _vk(key)
        self._user32.keybd_event(vk, 0, 0x0002, 0)

    def tap_key(self, key: str) -> None:
        self.press_key(key)
        self.release_key(key)

    def hotkey(self, keys: list[str]) -> None:
        for key in keys:
            self.press_key(key)
        for key in reversed(keys):
            self.release_key(key)


class PynputBackend:
    def __init__(self):
        from pynput.keyboard import Controller as KeyController
        from pynput.keyboard import Key
        from pynput.mouse import Button
        from pynput.mouse import Controller as MouseController

        self._mouse = MouseController()
        self._keyboard = KeyController()
        self._button = Button
        self._key = Key

    def cursor(self) -> tuple[int, int]:
        x, y = self._mouse.position
        return int(x), int(y)

    def move(self, x: int, y: int) -> None:
        self._mouse.position = (int(x), int(y))

    def _btn(self, button: str):
        return {"left": self._button.left, "right": self._button.right, "middle": self._button.middle}[button]

    def mouse_press(self, button: str) -> None:
        self._mouse.press(self._btn(button))

    def mouse_release(self, button: str) -> None:
        self._mouse.release(self._btn(button))

    def click(self, button: str, count: int = 1, interval_ms: int = 40) -> None:
        self._mouse.click(self._btn(button), int(count))

    def _resolve(self, key: str):
        named = {
            "space": self._key.space,
            "enter": self._key.enter,
            "tab": self._key.tab,
            "esc": self._key.esc,
            "escape": self._key.esc,
            "backspace": self._key.backspace,
            "delete": self._key.delete,
            "up": self._key.up,
            "down": self._key.down,
            "left": self._key.left,
            "right": self._key.right,
            "shift": self._key.shift,
            "ctrl": self._key.ctrl,
            "alt": self._key.alt,
            "cmd": self._key.cmd,
            "win": self._key.cmd,
        }
        if key in named:
            return named[key]
        if key.startswith("f") and key[1:].isdigit():
            return getattr(self._key, key)
        return key

    def press_key(self, key: str) -> None:
        self._keyboard.press(self._resolve(key))

    def release_key(self, key: str) -> None:
        self._keyboard.release(self._resolve(key))

    def tap_key(self, key: str) -> None:
        self.press_key(key)
        self.release_key(key)

    def hotkey(self, keys: list[str]) -> None:
        for key in keys:
            self.press_key(key)
        for key in reversed(keys):
            self.release_key(key)


def create_backend(prefer_fake: bool = False) -> InputBackend:
    if prefer_fake:
        return FakeBackend()
    if sys.platform == "win32":
        try:
            return Win32Backend()
        except Exception:
            pass
    try:
        return PynputBackend()
    except Exception:
        return FakeBackend()


def _vk(key: str) -> int:
    named = {
        "space": 0x20,
        "enter": 0x0D,
        "tab": 0x09,
        "esc": 0x1B,
        "escape": 0x1B,
        "backspace": 0x08,
        "delete": 0x2E,
        "up": 0x26,
        "down": 0x28,
        "left": 0x25,
        "right": 0x27,
        "shift": 0x10,
        "ctrl": 0x11,
        "alt": 0x12,
        "win": 0x5B,
        "f1": 0x70,
        "f2": 0x71,
        "f3": 0x72,
        "f4": 0x73,
        "f5": 0x74,
        "f6": 0x75,
        "f7": 0x76,
        "f8": 0x77,
        "f9": 0x78,
        "f10": 0x79,
        "f11": 0x7A,
        "f12": 0x7B,
    }
    if key in named:
        return named[key]
    if len(key) == 1:
        return ord(key.upper())
    raise ValueError(f"Unsupported key '{key}'")
