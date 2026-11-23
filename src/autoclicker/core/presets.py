"""Built-in examples. They are real profiles, not placeholders."""

from __future__ import annotations

from autoclicker.core.models import ClickJob, Macro, MacroAction, Profile, Workflow, new_id


def builtin_profiles() -> list[Profile]:
    gentle = Profile(
        id="preset-gentle",
        name="Gentle cursor click",
        notes="Ten left clicks at the current cursor, one per second.",
        is_builtin=True,
        is_default=True,
        job=ClickJob(
            button="left",
            click_type="single",
            interval_ms=1000,
            repeat_mode="count",
            repeat_count=10,
            position_mode="cursor",
            user_confirmed=True,
        ),
    )
    menu = Profile(
        id="preset-right",
        name="Slow right click",
        notes="Fifty right clicks, two seconds apart, at a fixed point.",
        is_builtin=True,
        job=ClickJob(
            button="right",
            interval_ms=2000,
            repeat_mode="count",
            repeat_count=50,
            position_mode="fixed",
            x=640,
            y=400,
            user_confirmed=True,
        ),
    )
    points = Profile(
        id="preset-points",
        name="Three-point sequence",
        notes="Visits three saved points in order. Edit the coordinates before use.",
        is_builtin=True,
        job=ClickJob(
            button="left",
            interval_ms=500,
            repeat_mode="count",
            repeat_count=6,
            position_mode="multi",
            points=[[200, 200], [400, 200], [400, 400]],
            point_order="sequential",
            user_confirmed=True,
        ),
    )
    return [gentle, menu, points]


def builtin_macro() -> Macro:
    return Macro(
        id="preset-macro-pause",
        name="Example: click, wait, escape",
        speed=1.0,
        repeat=1,
        actions=[
            MacroAction("click", 0, {"button": "left", "action": "click", "x": 320, "y": 240}),
            MacroAction("delay", 0, {"ms": 400}),
            MacroAction("key", 400, {"key": "esc", "action": "tap"}),
        ],
    )


def builtin_workflow() -> Workflow:
    return Workflow(
        id="preset-workflow-pixel",
        name="Example: wait, then click if pixel matches",
        steps=[
            {"id": new_id(), "type": "wait", "ms": 200},
            {
                "id": new_id(),
                "type": "if",
                "when": {
                    "kind": "pixel",
                    "x": 1,
                    "y": 1,
                    "color": [10, 20, 30],
                    "tolerance": 8,
                },
                "then": [
                    {"id": new_id(), "type": "click", "button": "left", "x": 1, "y": 1, "times": 1}
                ],
                "else": [{"id": new_id(), "type": "wait", "ms": 50}],
            },
        ],
    )
