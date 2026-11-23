"""Application services. One automation worker may run at a time."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
import io

from autoclicker.core.engine import ClickEngine, EngineBusyError
from autoclicker.core.hotkeys import find_conflicts
from autoclicker.core.macro import MacroPlayer, MacroRecorder, validate_macro
from autoclicker.core.models import ClickJob, EngineStats, Macro, Profile, SafetyPolicy, Workflow
from autoclicker.core.safety import ValidationError, clamp_policy, validate_job
from autoclicker.core.workflow import WorkflowRunner, validate_workflow
from autoclicker.platform.hotkey_listener import HotkeyListener
from autoclicker.platform.input_backend import FakeBackend, create_backend
from autoclicker.platform.recorder_listener import RecorderListener
from autoclicker.platform.screen import ArrayScreen, create_screen
from autoclicker.storage.database import Database
from autoclicker.storage.exchange import ImportRejected, export_bundle, export_sessions_csv, export_sessions_json, load_document


class BusyAutomation(RuntimeError):
    pass


class EmergencyLatched(RuntimeError):
    pass


class Controller:
    def __init__(self, db: Database, backend=None, screen=None, enable_hooks: bool = True):
        self.db = db
        self.backend = backend or create_backend()
        self.screen = screen or create_screen()
        self.policy = clamp_policy(db.load_safety())
        self.engine = ClickEngine(self.backend, self.policy)
        self.player = MacroPlayer(self.backend, self.policy)
        self.runner = WorkflowRunner(self.backend, self.policy, self.screen)
        self.recorder = MacroRecorder()
        self._record_listener = RecorderListener(self.recorder)
        self.hotkeys = HotkeyListener()
        self.emergency_latched = False
        self.capture_enabled = False
        self.latest = EngineStats()
        self._lock = threading.Lock()
        self._session_open = False
        self._session_started = ""
        self._session_kind = ""
        self._session_name = ""
        self.engine.listeners.append(self._on_engine)
        self._enable_hooks = enable_hooks
        self._shut = False
        if enable_hooks:
            self.apply_hotkeys()

    def snapshot(self) -> EngineStats:
        return EngineStats(**self.latest.to_dict())

    def _guard_start(self) -> None:
        if self.emergency_latched:
            raise EmergencyLatched("Emergency stop is latched. Clear it before starting again.")
        if self.engine.is_running or self.player.is_running or self.runner.is_running:
            raise BusyAutomation("Stop the active automation before starting another one.")

    def start_job(self, job: ClickJob, profile_name: str = "Manual") -> None:
        self._guard_start()
        errors = validate_job(job, self.policy)
        if errors:
            raise ValidationError(errors)
        self._open_session(profile_name, "click")
        self.engine.start(job, profile_name)
        self.db.log_activity(f"Started clicking · {profile_name}")

    def start_profile(self, profile_id: str) -> None:
        profile = self.db.profile(profile_id)
        if profile is None:
            raise KeyError(profile_id)
        self.start_job(profile.job, profile.name)

    def start_macro(self, macro: Macro) -> None:
        self._guard_start()
        errors = validate_macro(macro, self.policy)
        if errors:
            raise ValidationError(errors)
        self._open_session(macro.name, "macro")
        self.player.start(macro)
        self.db.log_activity(f"Playing macro · {macro.name}")

    def start_workflow(self, workflow: Workflow) -> None:
        self._guard_start()
        errors = validate_workflow(workflow.steps, self.policy)
        if errors:
            raise ValidationError(errors)
        if not self.capture_enabled and _needs_capture(workflow.steps):
            raise RuntimeError("Enable screen capture in Smart Automation before running image or pixel steps.")
        self.runner.templates = self._load_templates(workflow.steps)
        self._open_session(workflow.name, "workflow")
        self.runner.start(workflow.steps)
        self.db.log_activity(f"Started workflow · {workflow.name}")

    def pause(self) -> None:
        self.engine.pause()
        self.player.pause()
        self.runner.pause()
        self.db.log_activity("Paused automation")

    def resume(self) -> None:
        if self.emergency_latched:
            raise EmergencyLatched("Emergency stop is latched.")
        self.engine.resume()
        self.player.resume()
        self.runner.resume()
        self.db.log_activity("Resumed automation")

    def stop(self) -> None:
        self.engine.stop()
        self.player.stop()
        self.runner.stop()
        self._close_macro_or_workflow("stopped")
        self.db.log_activity("Stop requested")

    def emergency_stop(self) -> None:
        self.emergency_latched = True
        self.engine.stop()
        self.player.stop()
        self.runner.stop()
        self.recorder.recording = False
        self._record_listener.stop()
        self._close_macro_or_workflow("emergency")
        self.db.log_activity("Emergency stop", level="warning")

    def clear_emergency(self) -> None:
        self.emergency_latched = False
        self.db.log_activity("Emergency latch cleared")

    def clear_tasks(self) -> None:
        self.stop()
        self.engine.join(2)
        self.player.join(2)
        self.runner.join(2)

    def shutdown(self) -> None:
        if self._shut:
            return
        self._shut = True
        self.emergency_stop()
        self.emergency_latched = False
        self.engine.join(2)
        self.player.join(2)
        self.runner.join(2)
        self.hotkeys.stop()
        self._record_listener.stop()
        self.db.close()

    def _open_session(self, name: str, kind: str) -> None:
        self._session_open = True
        self._session_started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._session_kind = kind
        self._session_name = name

    def _on_engine(self, stats: EngineStats) -> None:
        with self._lock:
            self.latest = stats
        if stats.state == "idle" and self._session_open and self._session_kind == "click":
            self._session_open = False
            self.db.add_session(
                profile_name=self._session_name,
                kind="click",
                started_at=self._session_started,
                clicks=stats.clicks,
                duration_ms=int(stats.elapsed_ms),
                reason=stats.message or "completed",
            )
            self.db.log_activity(
                f"Click session ended · {stats.clicks} clicks · {stats.message or 'completed'}"
            )

    def _close_macro_or_workflow(self, reason: str) -> None:
        if self._session_open and self._session_kind in {"macro", "workflow"}:
            self._session_open = False
            self.db.add_session(
                profile_name=self._session_name,
                kind=self._session_kind,
                started_at=self._session_started,
                clicks=0,
                duration_ms=0,
                reason=reason,
            )

    def note_macro_finished(self) -> None:
        if self._session_open and self._session_kind == "macro" and not self.player.is_running:
            self._close_macro_or_workflow(self.player.message or "completed")

    def note_workflow_finished(self) -> None:
        if self._session_open and self._session_kind == "workflow" and not self.runner.is_running:
            self._close_macro_or_workflow(self.runner.message or "completed")

    def cursor(self) -> tuple[int, int]:
        try:
            return self.backend.cursor()
        except Exception:
            return (0, 0)

    def update_safety(self, policy: SafetyPolicy) -> SafetyPolicy:
        policy = clamp_policy(policy)
        self.policy = policy
        self.engine.set_policy(policy)
        self.player.policy = policy
        self.runner.policy = policy
        self.db.save_safety(policy)
        return policy

    def hotkey_map(self) -> dict[str, str]:
        raw = self.db.get_setting("hotkeys") or "{}"
        data = json.loads(raw)
        return {str(k): str(v) for k, v in data.items()}

    def set_hotkeys(self, bindings: dict[str, str]) -> list[str]:
        conflicts = find_conflicts(bindings)
        if conflicts:
            return conflicts
        self.db.set_setting("hotkeys", json.dumps(bindings))
        if self._enable_hooks:
            self.apply_hotkeys()
        return []

    def apply_hotkeys(self) -> str | None:
        return self.hotkeys.restart(self.hotkey_map(), self._on_hotkey)

    def _on_hotkey(self, action: str) -> None:
        try:
            if action == "start":
                profile = self.db.default_profile()
                if profile:
                    self.start_profile(profile.id)
            elif action == "pause":
                self.pause()
            elif action == "resume":
                self.resume()
            elif action == "stop":
                self.stop()
            elif action == "emergency":
                self.emergency_stop()
            elif action == "profile":
                profile = self.db.default_profile()
                if profile:
                    self.start_profile(profile.id)
            elif action.startswith("profile:"):
                self.start_profile(action.split(":", 1)[1])
        except (ValidationError, BusyAutomation, EmergencyLatched, EngineBusyError) as exc:
            self.db.log_activity(str(exc), level="warning")

    def begin_recording(self) -> str | None:
        if self.recorder.recording:
            return "Already recording"
        self.recorder.start()
        return self._record_listener.start()

    def finish_recording(self, name: str) -> Macro:
        macro = self.recorder.stop(name)
        self._record_listener.stop()
        return macro

    def import_text(self, raw: str) -> dict:
        loaded = load_document(raw, self.policy)
        for profile in loaded["profiles"]:
            self.db.save_profile(profile)
        for macro in loaded["macros"]:
            self.db.save_macro(macro)
        for workflow in loaded["workflows"]:
            self.db.save_workflow(workflow)
        self.db.log_activity(
            f"Imported {len(loaded['profiles'])} profiles, {len(loaded['macros'])} macros"
        )
        return loaded

    def export_all(self) -> str:
        return export_bundle(self.db.profiles(), self.db.macros(), self.db.workflows())

    def export_stats(self, kind: str) -> str:
        rows = self.db.sessions(1000)
        if kind == "csv":
            return export_sessions_csv(rows)
        return export_sessions_json(rows)

    def store_template(self, name: str, png: bytes) -> str:
        image = _decode_image(png)
        self.capture_enabled = True
        return self.db.save_template(name, png)

    def _load_templates(self, steps: list) -> dict[str, np.ndarray]:
        found: dict[str, np.ndarray] = {}
        def walk(items):
            for step in items:
                if not isinstance(step, dict):
                    continue
                template_id = step.get("template_id") or (step.get("when") or {}).get("template_id")
                if template_id and template_id not in found:
                    blob = self.db.template_png(str(template_id))
                    if blob:
                        found[str(template_id)] = _decode_image(blob)
                for key in ("steps", "then", "else"):
                    if isinstance(step.get(key), list):
                        walk(step[key])
                when = step.get("when")
                if isinstance(when, dict) and when.get("template_id"):
                    pass
        walk(steps)
        return found


def _needs_capture(steps: list) -> bool:
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("type") in {"image", "pixel"}:
            return True
        when = step.get("when") or {}
        if isinstance(when, dict) and when.get("kind") in {"image", "not_image", "pixel"}:
            return True
        for key in ("steps", "then", "else"):
            if isinstance(step.get(key), list) and _needs_capture(step[key]):
                return True
    return False


def _decode_image(png: bytes) -> np.ndarray:
    if len(png) > 1_500_000:
        raise ValueError("Image is larger than 1.5 MB")
    try:
        with Image.open(io.BytesIO(png)) as handle:
            handle.verify()
        with Image.open(io.BytesIO(png)) as handle:
            rgb = handle.convert("RGB")
            if rgb.width > 800 or rgb.height > 800 or rgb.width < 1 or rgb.height < 1:
                raise ValueError("Image must be between 1×1 and 800×800")
            return np.array(rgb)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Image is not a readable PNG or JPEG") from exc


def open_controller(data_dir: Path, *, testing: bool = False) -> Controller:
    db = Database(data_dir / "autoclicker.db")
    if testing:
        return Controller(db, backend=FakeBackend(), screen=ArrayScreen(np.zeros((8, 8, 3), dtype=np.uint8)), enable_hooks=False)
    return Controller(db)
