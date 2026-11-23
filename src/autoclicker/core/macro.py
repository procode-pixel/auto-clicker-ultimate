"""Macro recording model, editor operations, and timed playback."""

from __future__ import annotations

import threading
import time
from typing import Callable

from autoclicker.core.models import Macro, MacroAction, SafetyPolicy
from autoclicker.core.safety import ValidationError

ALLOWED_TYPES = {"move", "click", "key", "hotkey", "delay", "loop"}
FORBIDDEN_KEYS = {
    "code",
    "exec",
    "eval",
    "shell",
    "command",
    "python",
    "script",
    "path",
    "url",
    "import",
    "file",
}
KEY_PATTERN_OK = set("abcdefghijklmnopqrstuvwxyz0123456789_+-")
NAMED_KEYS = {
    "space",
    "enter",
    "tab",
    "esc",
    "escape",
    "backspace",
    "delete",
    "up",
    "down",
    "left",
    "right",
    "home",
    "end",
    "page_up",
    "page_down",
    "shift",
    "ctrl",
    "alt",
    "cmd",
    "win",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
}


class MacroRecorder:
    """Turns input events into a timeline. Movement is throttled."""

    def __init__(self, move_gap_ms: int = 30, move_deadzone: int = 4):
        self.move_gap_ms = move_gap_ms
        self.move_deadzone = move_deadzone
        self.actions: list[MacroAction] = []
        self.recording = False
        self._t0 = 0.0

    def start(self) -> None:
        self.actions = []
        self._t0 = time.perf_counter()
        self.recording = True

    def stop(self, name: str = "Recorded macro") -> Macro:
        self.recording = False
        from autoclicker.core.models import new_id

        return Macro(id=new_id(), name=name, actions=list(self.actions))

    def _stamp(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)

    def add(self, kind: str, **params) -> None:
        if not self.recording:
            return
        if kind == "move" and self.actions:
            last = self.actions[-1]
            if last.type == "move":
                same_gap = self._stamp() - last.t < self.move_gap_ms
                dx = abs(int(params.get("x", 0)) - int(last.params.get("x", 0)))
                dy = abs(int(params.get("y", 0)) - int(last.params.get("y", 0)))
                if same_gap or (dx <= self.move_deadzone and dy <= self.move_deadzone):
                    last.params.update(params)
                    last.t = self._stamp()
                    return
        self.actions.append(MacroAction(kind, self._stamp(), params))


def delete_action(actions: list[MacroAction], index: int) -> list[MacroAction]:
    if not 0 <= index < len(actions):
        raise IndexError("Action index out of range")
    return [a for i, a in enumerate(actions) if i != index]


def duplicate_action(actions: list[MacroAction], index: int) -> list[MacroAction]:
    if not 0 <= index < len(actions):
        raise IndexError("Action index out of range")
    clone = MacroAction(actions[index].type, actions[index].t, dict(actions[index].params))
    out = list(actions)
    out.insert(index + 1, clone)
    return out


def reorder_action(actions: list[MacroAction], index: int, new_index: int) -> list[MacroAction]:
    if not 0 <= index < len(actions) or not 0 <= new_index < len(actions):
        raise IndexError("Action index out of range")
    out = list(actions)
    item = out.pop(index)
    out.insert(new_index, item)
    return out


def insert_delay(actions: list[MacroAction], index: int, ms: int) -> list[MacroAction]:
    if ms < 0 or ms > 86_400_000:
        raise ValueError("Delay out of range")
    if not 0 <= index <= len(actions):
        raise IndexError("Action index out of range")
    stamp = actions[index - 1].t if index else 0
    out = list(actions)
    out.insert(index, MacroAction("delay", stamp, {"ms": int(ms)}))
    return out


def update_action(actions: list[MacroAction], index: int, **params) -> list[MacroAction]:
    if not 0 <= index < len(actions):
        raise IndexError("Action index out of range")
    out = list(actions)
    current = out[index]
    merged = dict(current.params)
    merged.update(params)
    out[index] = MacroAction(current.type, current.t, merged)
    return out


def wrap_loop(actions: list[MacroAction], start: int, end: int, count: int) -> list[MacroAction]:
    if count < 2 or count > 10_000:
        raise ValueError("Loop count must be between 2 and 10000")
    if not 0 <= start <= end < len(actions):
        raise IndexError("Loop range is invalid")
    body = actions[start : end + 1]
    loop = MacroAction("loop", body[0].t, {"count": int(count), "actions": [a.to_dict() for a in body]})
    return actions[:start] + [loop] + actions[end + 1 :]


def _count_actions(actions: list[dict], depth: int = 0) -> int:
    if depth > 8:
        raise ValidationError(["Macro nesting is too deep"])
    total = 0
    for action in actions:
        total += 1
        if action.get("type") == "loop":
            total += _count_actions(action.get("actions") or [], depth + 1) * max(
                1, int(action.get("count") or 1)
            )
    return total


def _validate_action(action: dict, policy: SafetyPolicy, depth: int = 0) -> list[str]:
    errors: list[str] = []
    if depth > 6:
        return ["Macro nesting is too deep"]
    if not isinstance(action, dict):
        return ["Each macro action must be an object"]
    extra = FORBIDDEN_KEYS.intersection(action.keys())
    if extra:
        return [f"Macro action contains forbidden fields: {', '.join(sorted(extra))}"]
    kind = action.get("type")
    if kind not in ALLOWED_TYPES:
        return [f"Unknown macro action '{kind}'"]
    if kind == "move":
        errors += _coord_errors(action)
    elif kind == "click":
        if action.get("button", "left") not in {"left", "right", "middle"}:
            errors.append("Macro click has an unknown button")
        press = action.get("action", "click")
        if press not in {"click", "press", "release"}:
            errors.append("Macro click action must be click, press, or release")
        if "x" in action or "y" in action:
            errors += _coord_errors(action)
    elif kind == "key":
        if not _key_ok(str(action.get("key", ""))):
            errors.append("Macro key is not allowed")
        if action.get("action", "tap") not in {"tap", "press", "release"}:
            errors.append("Key action must be tap, press, or release")
    elif kind == "hotkey":
        keys = action.get("keys") or []
        if not isinstance(keys, list) or not 1 <= len(keys) <= 4:
            errors.append("A hotkey needs 1 to 4 keys")
        elif any(not _key_ok(str(key)) for key in keys):
            errors.append("Hotkey contains a key that is not allowed")
    elif kind == "delay":
        ms = int(action.get("ms") or 0)
        if ms < 0 or ms > 86_400_000:
            errors.append("Delay is out of range")
    elif kind == "loop":
        count = int(action.get("count") or 0)
        if not 2 <= count <= policy.max_loop_count:
            errors.append("Loop count is out of range")
        nested = action.get("actions") or []
        if not nested:
            errors.append("A loop needs at least one action")
        if not _loop_has_delay(nested):
            errors.append("A loop must contain a delay so it cannot spin forever")
        for child in nested:
            errors += _validate_action(child, policy, depth + 1)
    return errors


def _loop_has_delay(actions: list[dict]) -> bool:
    for action in actions:
        if action.get("type") == "delay" and int(action.get("ms") or 0) >= 10:
            return True
        if action.get("type") == "loop" and _loop_has_delay(action.get("actions") or []):
            return True
    return False


def _coord_errors(action: dict) -> list[str]:
    errors = []
    for axis in ("x", "y"):
        if axis not in action:
            continue
        value = int(action[axis])
        if not -32_000 <= value <= 32_000:
            errors.append(f"Coordinate {axis} is out of range")
    return errors


def _key_ok(key: str) -> bool:
    if key in NAMED_KEYS:
        return True
    if not 1 <= len(key) <= 32:
        return False
    return all(ch in KEY_PATTERN_OK for ch in key)


def validate_macro(macro: Macro, policy: SafetyPolicy) -> list[str]:
    raw = [a.to_dict() for a in macro.actions]
    errors: list[str] = []
    if not macro.name.strip():
        errors.append("Macro name is required")
    if len(macro.name) > 80:
        errors.append("Macro name is too long")
    if not 0.25 <= float(macro.speed) <= 5:
        errors.append("Playback speed must be between 0.25 and 5")
    if not 1 <= int(macro.repeat) <= 10_000:
        errors.append("Macro repeat must be between 1 and 10000")
    try:
        count = _count_actions(raw)
    except ValidationError as exc:
        return errors + exc.errors
    if count > policy.max_macro_actions:
        errors.append(f"Macro expands to {count} actions, above the limit")
    for action in raw:
        errors += _validate_action(action, policy)
    return errors


class MacroPlayer:
    def __init__(self, backend, policy: SafetyPolicy, sleeper: Callable[[float], None] | None = None):
        self.backend = backend
        self.policy = policy
        self._sleep = sleeper or time.sleep
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread: threading.Thread | None = None
        self.state = "idle"
        self.message = ""

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, macro: Macro) -> None:
        errors = validate_macro(macro, self.policy)
        if errors:
            raise ValidationError(errors)
        if self.is_running:
            raise RuntimeError("A macro is already playing")
        self._stop.clear()
        self._pause.clear()
        self.state = "running"
        self._thread = threading.Thread(
            target=self._run, args=(macro,), name="macro-player", daemon=True
        )
        self._thread.start()

    def pause(self) -> None:
        self._pause.set()
        if self.is_running:
            self.state = "paused"

    def resume(self) -> None:
        self._pause.clear()
        if self.is_running:
            self.state = "running"

    def stop(self) -> None:
        self._stop.set()
        self._pause.clear()

    def join(self, timeout: float = 3.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _wait(self, ms: float) -> bool:
        remaining = max(0.0, ms) / 1000.0
        while remaining > 0:
            if self._stop.is_set():
                return False
            if self._pause.is_set():
                self._sleep(0.02)
                continue
            step = min(0.02, remaining)
            self._sleep(step)
            remaining -= step
        return not self._stop.is_set()

    def _run(self, macro: Macro) -> None:
        try:
            speed = min(5.0, max(0.25, float(macro.speed)))
            for _ in range(int(macro.repeat)):
                if not self._play(macro.actions, speed, 0):
                    self.state = "idle"
                    self.message = "stopped"
                    return
            self.state = "idle"
            self.message = "completed"
        except Exception as exc:  # noqa: BLE001
            self.state = "idle"
            self.message = str(exc)

    def _play(self, actions: list[MacroAction], speed: float, origin: int) -> bool:
        cursor = origin
        for action in actions:
            if self._stop.is_set():
                return False
            while self._pause.is_set():
                if self._stop.is_set():
                    return False
                self._sleep(0.02)
            if action.type == "loop":
                nested = [
                    MacroAction.from_dict(item) for item in action.params.get("actions") or []
                ]
                for _ in range(int(action.params.get("count") or 1)):
                    if not self._play(nested, speed, cursor):
                        return False
                continue
            if action.type == "delay":
                if not self._wait(int(action.params.get("ms") or 0) / speed):
                    return False
                continue
            target = origin + int(action.t / speed)
            gap = target - cursor
            if gap > 0 and not self._wait(gap):
                return False
            cursor = max(cursor, target)
            self._execute(action)
        return True

    def _execute(self, action: MacroAction) -> None:
        if action.type == "move":
            self.backend.move(int(action.params["x"]), int(action.params["y"]))
        elif action.type == "click":
            if "x" in action.params and "y" in action.params:
                self.backend.move(int(action.params["x"]), int(action.params["y"]))
            kind = action.params.get("action", "click")
            button = action.params.get("button", "left")
            if kind == "press":
                self.backend.mouse_press(button)
            elif kind == "release":
                self.backend.mouse_release(button)
            else:
                self.backend.click(button, 1)
        elif action.type == "key":
            key = str(action.params["key"])
            kind = action.params.get("action", "tap")
            if kind == "press":
                self.backend.press_key(key)
            elif kind == "release":
                self.backend.release_key(key)
            else:
                self.backend.tap_key(key)
        elif action.type == "hotkey":
            self.backend.hotkey(list(action.params.get("keys") or []))
