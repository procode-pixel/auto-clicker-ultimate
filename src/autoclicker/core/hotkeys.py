"""Hotkey normalization and conflict checks. The hook itself lives in the platform layer."""

from __future__ import annotations

MODIFIERS = ("ctrl", "alt", "shift", "win")
ACTIONS = ("start", "pause", "resume", "stop", "emergency", "profile")

DEFAULT_BINDINGS = {
    "start": "f6",
    "pause": "f7",
    "resume": "f8",
    "stop": "f9",
    "emergency": "ctrl+shift+f12",
    "profile": "",
}


def normalize_combo(combo: str) -> str:
    if combo is None:
        return ""
    parts = [part.strip().lower() for part in str(combo).replace(" ", "").split("+") if part.strip()]
    if not parts:
        return ""
    aliases = {"control": "ctrl", "cmd": "win", "windows": "win", "escape": "esc", "return": "enter"}
    parts = [aliases.get(part, part) for part in parts]
    mods = [mod for mod in MODIFIERS if mod in parts]
    keys = [part for part in parts if part not in MODIFIERS]
    if len(keys) != 1:
        raise ValueError("A shortcut needs exactly one non-modifier key")
    key = keys[0]
    if not key.replace("_", "").isalnum() or len(key) > 16:
        raise ValueError("Shortcut key is not allowed")
    return "+".join(mods + [key])


def find_conflicts(bindings: dict[str, str]) -> list[str]:
    seen: dict[str, str] = {}
    conflicts: list[str] = []
    for action, combo in bindings.items():
        if action not in ACTIONS and not action.startswith("profile:"):
            conflicts.append(f"Unknown hotkey action '{action}'")
            continue
        if not combo:
            continue
        try:
            normal = normalize_combo(combo)
        except ValueError as exc:
            conflicts.append(f"{action}: {exc}")
            continue
        if normal in seen:
            conflicts.append(f"'{normal}' is assigned to both {seen[normal]} and {action}")
        else:
            seen[normal] = action
    if not bindings.get("emergency"):
        conflicts.append("Emergency stop must keep a shortcut")
    return conflicts
