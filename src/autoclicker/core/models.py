"""Shared data models. Serialized as plain JSON — never executable code."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


SCHEMA_VERSION = 1
BUTTONS = ("left", "right", "middle")
CLICK_TYPES = ("single", "double", "sequence")
POSITION_MODES = ("cursor", "fixed", "multi")
REPEAT_MODES = ("count", "infinite", "duration")
INTERVAL_MODES = ("fixed", "random")


def new_id() -> str:
    return uuid4().hex


@dataclass
class ClickJob:
    button: str = "left"
    click_type: str = "single"
    sequence: list[dict[str, Any]] = field(default_factory=list)
    interval_ms: int = 100
    interval_mode: str = "fixed"
    random_min_ms: int = 80
    random_max_ms: int = 180
    repeat_mode: str = "count"
    repeat_count: int = 10
    duration_ms: int = 5_000
    start_delay_ms: int = 0
    scheduled_epoch: float | None = None
    position_mode: str = "cursor"
    x: int = 0
    y: int = 0
    points: list[list[int]] = field(default_factory=list)
    point_order: str = "sequential"
    user_confirmed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClickJob:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in known}
        points = clean.get("points") or []
        clean["points"] = [[int(p[0]), int(p[1])] for p in points]
        seq = clean.get("sequence") or []
        clean["sequence"] = [dict(step) for step in seq]
        if clean.get("scheduled_epoch") is not None:
            clean["scheduled_epoch"] = float(clean["scheduled_epoch"])
        return cls(**clean)


@dataclass
class Profile:
    id: str
    name: str
    job: ClickJob
    notes: str = ""
    hotkey: str | None = None
    macro_id: str | None = None
    workflow_id: str | None = None
    is_builtin: bool = False
    is_default: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["job"] = self.job.to_dict()
        payload["schema"] = "autoclicker.profile"
        payload["version"] = SCHEMA_VERSION
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        job = ClickJob.from_dict(data.get("job") or {})
        return cls(
            id=str(data.get("id") or new_id()),
            name=str(data.get("name") or "Untitled"),
            job=job,
            notes=str(data.get("notes") or ""),
            hotkey=data.get("hotkey") or None,
            macro_id=data.get("macro_id") or None,
            workflow_id=data.get("workflow_id") or None,
            is_builtin=bool(data.get("is_builtin", False)),
            is_default=bool(data.get("is_default", False)),
        )


@dataclass
class MacroAction:
    type: str
    t: int = 0
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        body = {"type": self.type, "t": int(self.t)}
        body.update(self.params)
        return body

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MacroAction:
        params = {k: v for k, v in data.items() if k not in {"type", "t"}}
        return cls(type=str(data["type"]), t=int(data.get("t") or 0), params=params)


@dataclass
class Macro:
    id: str
    name: str
    actions: list[MacroAction] = field(default_factory=list)
    speed: float = 1.0
    repeat: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "autoclicker.macro",
            "version": SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "speed": self.speed,
            "repeat": self.repeat,
            "actions": [a.to_dict() for a in self.actions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Macro:
        actions = [MacroAction.from_dict(item) for item in data.get("actions") or []]
        return cls(
            id=str(data.get("id") or new_id()),
            name=str(data.get("name") or "Macro"),
            actions=actions,
            speed=float(data.get("speed") or 1.0),
            repeat=int(data.get("repeat") or 1),
        )


@dataclass
class Workflow:
    id: str
    name: str
    steps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "autoclicker.workflow",
            "version": SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "steps": self.steps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workflow:
        return cls(
            id=str(data.get("id") or new_id()),
            name=str(data.get("name") or "Workflow"),
            steps=list(data.get("steps") or []),
        )


@dataclass
class SafetyPolicy:
    min_interval_ms: int = 15
    max_cps: int = 25
    hard_max_cps: int = 80
    max_session_ms: int = 3_600_000
    hard_max_session_ms: int = 8 * 3_600_000
    allow_infinite: bool = True
    confirm_above_cps: int = 12
    max_macro_actions: int = 5_000
    max_workflow_steps: int = 200
    max_loop_count: int = 10_000
    max_import_bytes: int = 2_000_000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SafetyPolicy:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        clean = {k: data[k] for k in known if k in data}
        return cls(**clean)


@dataclass
class EngineStats:
    state: str = "idle"
    clicks: int = 0
    cycles: int = 0
    elapsed_ms: float = 0.0
    cps: float = 0.0
    profile_name: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
