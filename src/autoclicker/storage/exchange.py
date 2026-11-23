"""Strict import and export. Imported files are data, never code."""

from __future__ import annotations

import json
from typing import Any

from autoclicker.core.models import Macro, Profile, SafetyPolicy, Workflow
from autoclicker.core.macro import validate_macro
from autoclicker.core.safety import validate_job
from autoclicker.core.workflow import validate_workflow

SCHEMAS = {
    "autoclicker.profile": Profile,
    "autoclicker.macro": Macro,
    "autoclicker.workflow": Workflow,
    "autoclicker.bundle": None,
}


class ImportRejected(ValueError):
    pass


def export_bundle(profiles: list[Profile], macros: list[Macro], workflows: list[Workflow]) -> str:
    payload = {
        "schema": "autoclicker.bundle",
        "version": 1,
        "profiles": [item.to_dict() for item in profiles],
        "macros": [item.to_dict() for item in macros],
        "workflows": [item.to_dict() for item in workflows],
    }
    return json.dumps(payload, indent=2)


def export_sessions_json(sessions: list[dict]) -> str:
    return json.dumps({"schema": "autoclicker.stats", "version": 1, "sessions": sessions}, indent=2)


def export_sessions_csv(sessions: list[dict]) -> str:
    header = "id,profile_name,kind,started_at,ended_at,clicks,duration_ms,reason"
    lines = [header]
    for row in sessions:
        values = [
            _csv(row.get("id")),
            _csv(row.get("profile_name")),
            _csv(row.get("kind")),
            _csv(row.get("started_at")),
            _csv(row.get("ended_at")),
            str(int(row.get("clicks") or 0)),
            str(int(row.get("duration_ms") or 0)),
            _csv(row.get("reason")),
        ]
        lines.append(",".join(values))
    return "\n".join(lines) + "\n"


def load_document(raw: str | bytes, policy: SafetyPolicy) -> dict[str, Any]:
    if isinstance(raw, str):
        data = raw.encode("utf-8")
    else:
        data = raw
    if len(data) > policy.max_import_bytes:
        raise ImportRejected("File exceeds the 2 MB import limit")
    try:
        text = data.decode("utf-8")
        parsed = json.loads(text)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ImportRejected("File is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise ImportRejected("The document root must be an object")
    schema = parsed.get("schema")
    version = parsed.get("version")
    if schema not in SCHEMAS:
        raise ImportRejected("Unknown file type")
    if version != 1:
        raise ImportRejected("Unsupported file version")
    if schema == "autoclicker.bundle":
        profiles = [_profile(item, policy) for item in parsed.get("profiles") or []]
        macros = [_macro(item, policy) for item in parsed.get("macros") or []]
        workflows = [_workflow(item, policy) for item in parsed.get("workflows") or []]
        return {"profiles": profiles, "macros": macros, "workflows": workflows}
    if schema == "autoclicker.profile":
        return {"profiles": [_profile(parsed, policy)], "macros": [], "workflows": []}
    if schema == "autoclicker.macro":
        return {"profiles": [], "macros": [_macro(parsed, policy)], "workflows": []}
    return {"profiles": [], "macros": [], "workflows": [_workflow(parsed, policy)]}


def _profile(data: dict, policy: SafetyPolicy) -> Profile:
    if not isinstance(data, dict) or data.get("schema") not in {None, "autoclicker.profile"}:
        raise ImportRejected("A profile entry is malformed")
    try:
        profile = Profile.from_dict(data)
    except (TypeError, ValueError) as exc:
        raise ImportRejected("A profile could not be read") from exc
    errors = validate_job(profile.job, policy)
    # Imported jobs are not yet confirmed by this user.
    profile.job.user_confirmed = False
    blocking = [err for err in errors if "confirmation" not in err]
    if blocking:
        raise ImportRejected("Profile failed validation: " + "; ".join(blocking))
    return profile


def _macro(data: dict, policy: SafetyPolicy) -> Macro:
    try:
        macro = Macro.from_dict(data)
    except (TypeError, ValueError, KeyError) as exc:
        raise ImportRejected("A macro could not be read") from exc
    errors = validate_macro(macro, policy)
    if errors:
        raise ImportRejected("Macro failed validation: " + "; ".join(errors))
    return macro


def _workflow(data: dict, policy: SafetyPolicy) -> Workflow:
    try:
        workflow = Workflow.from_dict(data)
    except (TypeError, ValueError) as exc:
        raise ImportRejected("A workflow could not be read") from exc
    errors = validate_workflow(workflow.steps, policy)
    if errors:
        raise ImportRejected("Workflow failed validation: " + "; ".join(errors))
    return workflow


def _csv(value: object) -> str:
    text = str(value or "").replace('"', "'").replace("\n", " ")
    return f'"{text}"'
