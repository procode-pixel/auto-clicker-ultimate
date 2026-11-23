"""Configuration guards. Hard ceilings cannot be raised from the interface."""

from __future__ import annotations

from autoclicker.core.models import (
    BUTTONS,
    CLICK_TYPES,
    INTERVAL_MODES,
    POSITION_MODES,
    REPEAT_MODES,
    ClickJob,
    SafetyPolicy,
)


class ValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def estimated_min_interval(job: ClickJob) -> int:
    if job.interval_mode == "random":
        return int(job.random_min_ms)
    return int(job.interval_ms)


def estimated_cps(job: ClickJob) -> float:
    interval = estimated_min_interval(job)
    if interval <= 0:
        return float("inf")
    clicks_per_cycle = 1
    if job.click_type == "double":
        clicks_per_cycle = 2
    elif job.click_type == "sequence":
        clicks_per_cycle = sum(int(step.get("times", 1)) for step in job.sequence) or 1
    return (1000.0 / interval) * clicks_per_cycle


def validate_job(job: ClickJob, policy: SafetyPolicy) -> list[str]:
    errors: list[str] = []
    if job.button not in BUTTONS:
        errors.append("Mouse button must be left, right, or middle")
    if job.click_type not in CLICK_TYPES:
        errors.append("Click type is not supported")
    if job.interval_mode not in INTERVAL_MODES:
        errors.append("Interval mode must be fixed or random")
    if job.repeat_mode not in REPEAT_MODES:
        errors.append("Repeat mode is not supported")
    if job.position_mode not in POSITION_MODES:
        errors.append("Position mode is not supported")
    if job.point_order not in {"sequential", "random"}:
        errors.append("Point order must be sequential or random")

    if job.interval_mode == "fixed":
        if job.interval_ms < policy.min_interval_ms:
            errors.append(
                f"Interval must be at least {policy.min_interval_ms} ms"
            )
    else:
        if job.random_min_ms < policy.min_interval_ms:
            errors.append(
                f"Random minimum must be at least {policy.min_interval_ms} ms"
            )
        if job.random_max_ms < job.random_min_ms:
            errors.append("Random maximum must be greater than or equal to the minimum")
        if job.random_max_ms > 86_400_000:
            errors.append("Random maximum is too large")

    cps = estimated_cps(job)
    if cps > policy.hard_max_cps:
        errors.append(
            f"Click rate {cps:.1f}/s exceeds the hard limit of {policy.hard_max_cps}/s"
        )
    elif cps > policy.max_cps:
        errors.append(
            f"Click rate {cps:.1f}/s exceeds the configured maximum of {policy.max_cps}/s"
        )

    needs_confirm = cps >= policy.confirm_above_cps or job.repeat_mode == "infinite"
    if needs_confirm and not job.user_confirmed:
        errors.append("This configuration needs explicit confirmation before it can start")

    if job.repeat_mode == "count":
        if not 1 <= int(job.repeat_count) <= 1_000_000:
            errors.append("Click count must be between 1 and 1,000,000")
    elif job.repeat_mode == "infinite" and not policy.allow_infinite:
        errors.append("Infinite clicking is disabled in Safety")
    elif job.repeat_mode == "duration":
        if job.duration_ms < policy.min_interval_ms:
            errors.append("Duration is shorter than the minimum interval")
        if job.duration_ms > policy.max_session_ms:
            errors.append("Duration exceeds the maximum session length")

    if job.start_delay_ms < 0 or job.start_delay_ms > 86_400_000:
        errors.append("Start delay must be between 0 and 24 hours")

    if job.position_mode == "fixed":
        if not _coord_ok(job.x) or not _coord_ok(job.y):
            errors.append("Fixed coordinates are out of range")
    elif job.position_mode == "multi":
        if not job.points:
            errors.append("Add at least one saved position")
        if len(job.points) > 500:
            errors.append("A profile can store at most 500 positions")
        for point in job.points:
            if len(point) != 2 or not _coord_ok(point[0]) or not _coord_ok(point[1]):
                errors.append("A saved position is out of range")
                break

    if job.click_type == "sequence":
        if not job.sequence or len(job.sequence) > 50:
            errors.append("A click sequence needs 1 to 50 steps")
        for step in job.sequence:
            if step.get("button") not in BUTTONS:
                errors.append("Sequence step has an unknown button")
                break
            times = int(step.get("times", 1))
            if not 1 <= times <= 5:
                errors.append("Each sequence step can click 1 to 5 times")
                break

    if job.scheduled_epoch is not None and job.scheduled_epoch < 0:
        errors.append("Scheduled time is invalid")

    return errors


def clamp_policy(policy: SafetyPolicy) -> SafetyPolicy:
    """User settings can tighten limits, never loosen the hard ceilings."""
    policy.min_interval_ms = max(15, int(policy.min_interval_ms))
    policy.hard_max_cps = 80
    policy.hard_max_session_ms = 8 * 3_600_000
    policy.max_cps = min(policy.hard_max_cps, max(1, int(policy.max_cps)))
    policy.max_session_ms = min(
        policy.hard_max_session_ms, max(1_000, int(policy.max_session_ms))
    )
    policy.confirm_above_cps = min(policy.max_cps, max(1, int(policy.confirm_above_cps)))
    policy.max_macro_actions = min(5_000, max(1, int(policy.max_macro_actions)))
    policy.max_workflow_steps = min(200, max(1, int(policy.max_workflow_steps)))
    policy.max_loop_count = min(10_000, max(1, int(policy.max_loop_count)))
    policy.max_import_bytes = 2_000_000
    return policy


def _coord_ok(value: int) -> bool:
    return -32_000 <= int(value) <= 32_000
