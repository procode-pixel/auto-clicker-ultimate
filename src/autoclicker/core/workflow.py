"""Visual automation runner. Loops are finite and must contain a delay."""

from __future__ import annotations

import threading
import time
from typing import Callable

import numpy as np

from autoclicker.core.models import SafetyPolicy
from autoclicker.core.recognition import crop, find_template, pixel_matches
from autoclicker.core.safety import ValidationError

STEP_TYPES = {
    "click",
    "move",
    "key",
    "hotkey",
    "wait",
    "repeat",
    "if",
    "image",
    "pixel",
    "stop",
    "set_flag",
}
FORBIDDEN_KEYS = {
    "code",
    "exec",
    "eval",
    "shell",
    "command",
    "python",
    "script",
    "url",
    "import",
}


def validate_workflow(steps: list[dict], policy: SafetyPolicy) -> list[str]:
    errors: list[str] = []
    if len(steps) > policy.max_workflow_steps:
        errors.append("Workflow has too many steps")
    errors += _walk(steps, policy, depth=0)
    return errors


def _walk(steps: list, policy: SafetyPolicy, depth: int) -> list[str]:
    if depth > 6:
        return ["Workflow nesting is too deep"]
    if not isinstance(steps, list):
        return ["Steps must be a list"]
    errors: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            errors.append("Each step must be an object")
            continue
        extra = FORBIDDEN_KEYS.intersection(step.keys())
        if extra:
            errors.append("A step contains a forbidden field")
            continue
        kind = step.get("type")
        if kind not in STEP_TYPES:
            errors.append(f"Unknown step type '{kind}'")
            continue
        if kind == "wait":
            ms = int(step.get("ms") or 0)
            if ms < policy.min_interval_ms or ms > 86_400_000:
                errors.append("Wait is outside the allowed range")
        elif kind == "repeat":
            count = int(step.get("count") or 0)
            body = step.get("steps") or []
            if not 2 <= count <= policy.max_loop_count:
                errors.append("Repeat count is out of range")
            if not _contains_wait(body, policy.min_interval_ms):
                errors.append("Repeat must include a wait so it cannot spin")
            errors += _walk(body, policy, depth + 1)
        elif kind == "if":
            errors += _validate_condition(step.get("when") or {})
            errors += _walk(step.get("then") or [], policy, depth + 1)
            errors += _walk(step.get("else") or [], policy, depth + 1)
        elif kind == "click":
            if step.get("button", "left") not in {"left", "right", "middle"}:
                errors.append("Click step has an unknown button")
        elif kind == "image":
            if not step.get("template_id"):
                errors.append("Image step needs a reference image")
            confidence = float(step.get("confidence") or 0)
            if not 0.1 <= confidence <= 0.99:
                errors.append("Image confidence must be between 0.10 and 0.99")
        elif kind == "pixel":
            color = step.get("color") or []
            if len(color) != 3 or any(not 0 <= int(c) <= 255 for c in color):
                errors.append("Pixel color must be three channels from 0 to 255")
            if not 0 <= int(step.get("tolerance") or 0) <= 255:
                errors.append("Pixel tolerance is out of range")
        elif kind in {"move", "key", "hotkey", "stop", "set_flag"}:
            if kind == "set_flag" and not str(step.get("name") or "").strip():
                errors.append("Flag name is required")
            if kind == "key" and not str(step.get("key") or "").strip():
                errors.append("Key is required")
    return errors


def _contains_wait(steps: list, minimum: int) -> bool:
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("type") == "wait" and int(step.get("ms") or 0) >= minimum:
            return True
        if step.get("type") in {"repeat", "if"}:
            if _contains_wait(step.get("steps") or step.get("then") or [], minimum):
                return True
            if _contains_wait(step.get("else") or [], minimum):
                return True
    return False


def _validate_condition(when: dict) -> list[str]:
    kind = when.get("kind")
    if kind not in {"image", "not_image", "pixel", "timer", "flag"}:
        return ["Condition type is not supported"]
    if kind in {"image", "not_image"} and not when.get("template_id"):
        return ["Image condition needs a reference image"]
    if kind == "timer" and int(when.get("ms") or 0) < 0:
        return ["Timer condition is invalid"]
    if kind == "flag" and not str(when.get("name") or "").strip():
        return ["Flag condition needs a name"]
    return []


class WorkflowRunner:
    def __init__(self, backend, policy: SafetyPolicy, screen, templates: dict[str, np.ndarray] | None = None):
        self.backend = backend
        self.policy = policy
        self.screen = screen
        self.templates = templates or {}
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread: threading.Thread | None = None
        self.state = "idle"
        self.message = ""
        self.last_match: dict | None = None
        self.flags: dict[str, bool] = {}
        self._started = 0.0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, steps: list[dict]) -> None:
        errors = validate_workflow(steps, self.policy)
        if errors:
            raise ValidationError(errors)
        if self.is_running:
            raise RuntimeError("A workflow is already running")
        self._stop.clear()
        self._pause.clear()
        self.flags = {}
        self.last_match = None
        self.state = "running"
        self._thread = threading.Thread(
            target=self._run, args=(steps,), name="workflow-runner", daemon=True
        )
        self._thread.start()

    def run_inline(self, steps: list[dict]) -> str:
        """Synchronous run used by tests."""
        errors = validate_workflow(steps, self.policy)
        if errors:
            raise ValidationError(errors)
        self._stop.clear()
        self._pause.clear()
        self.flags = {}
        self._started = time.perf_counter()
        self.state = "running"
        reason = self._execute(steps)
        self.state = "idle"
        self.message = reason
        return reason

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
                time.sleep(0.02)
                continue
            step = min(0.02, remaining)
            time.sleep(step)
            remaining -= step
        return not self._stop.is_set()

    def _run(self, steps: list[dict]) -> None:
        self._started = time.perf_counter()
        try:
            reason = self._execute(steps)
        except Exception as exc:  # noqa: BLE001
            reason = str(exc)
        self.state = "idle"
        self.message = reason

    def _execute(self, steps: list[dict]) -> str:
        for step in steps:
            if self._stop.is_set():
                return "stopped"
            while self._pause.is_set():
                if self._stop.is_set():
                    return "stopped"
                time.sleep(0.02)
            outcome = self._one(step)
            if outcome == "stop":
                return "stopped"
            if outcome == "halted":
                return "stopped"
        return "completed"

    def _one(self, step: dict) -> str:
        kind = step["type"]
        if kind == "stop":
            return "stop"
        if kind == "wait":
            return "ok" if self._wait(int(step["ms"])) else "halted"
        if kind == "move":
            self.backend.move(int(step["x"]), int(step["y"]))
        elif kind == "click":
            if "x" in step and "y" in step:
                self.backend.move(int(step["x"]), int(step["y"]))
            self.backend.click(step.get("button", "left"), int(step.get("times", 1)))
        elif kind == "key":
            self.backend.tap_key(str(step["key"]))
        elif kind == "hotkey":
            self.backend.hotkey(list(step.get("keys") or []))
        elif kind == "set_flag":
            self.flags[str(step["name"])] = True
        elif kind == "repeat":
            for _ in range(int(step["count"])):
                reason = self._execute(step.get("steps") or [])
                if reason != "completed":
                    return "halted" if reason == "stopped" else reason
        elif kind == "if":
            branch = "then" if self._condition(step.get("when") or {}) else "else"
            reason = self._execute(step.get(branch) or [])
            if reason != "completed":
                return "halted" if reason == "stopped" else reason
        elif kind == "pixel":
            matched = self._pixel(step)
            self.last_match = {"type": "pixel", "matched": matched}
            if matched and step.get("click") and "x" in step and "y" in step:
                self.backend.move(int(step["x"]), int(step["y"]))
                self.backend.click(step.get("button", "left"), 1)
        elif kind == "image":
            match = self._image(step)
            self.last_match = None if match is None else {
                "type": "image",
                "x": match.x,
                "y": match.y,
                "confidence": match.confidence,
            }
            action = step.get("on_found", "continue")
            if match is not None and action == "click_center":
                cx, cy = match.center
                self.backend.move(cx, cy)
                self.backend.click(step.get("button", "left"), 1)
            elif match is not None and action == "stop":
                return "stop"
            elif match is None and step.get("on_missing") == "stop":
                return "stop"
        return "ok"

    def _condition(self, when: dict) -> bool:
        kind = when.get("kind")
        if kind == "timer":
            return (time.perf_counter() - self._started) * 1000 >= int(when.get("ms") or 0)
        if kind == "flag":
            return bool(self.flags.get(str(when.get("name"))))
        if kind == "pixel":
            return self._pixel(when)
        if kind == "image":
            return self._image(when) is not None
        if kind == "not_image":
            return self._image(when) is None
        return False

    def _grab(self, region) -> np.ndarray:
        image = self.screen.grab(region)
        return np.asarray(image)

    def _pixel(self, step: dict) -> bool:
        region = step.get("region")
        image = self._grab(tuple(region) if region else None)
        x, y = int(step.get("x", 0)), int(step.get("y", 0))
        if region:
            x -= int(region[0])
            y -= int(region[1])
        color = tuple(int(c) for c in step["color"])
        return pixel_matches(image, x, y, color, int(step.get("tolerance") or 0))

    def _image(self, step: dict):
        template = self.templates.get(str(step.get("template_id")))
        if template is None:
            return None
        region = step.get("region")
        image = self._grab(tuple(region) if region else None)
        offset = (0, 0)
        if region:
            image, offset = crop(image, (0, 0, int(region[2]), int(region[3])))
            offset = (int(region[0]), int(region[1]))
        return find_template(
            image,
            template,
            float(step.get("confidence") or 0.8),
            offset=offset,
        )
