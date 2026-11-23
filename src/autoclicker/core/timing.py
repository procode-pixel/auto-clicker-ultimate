"""Interval math. Hours, minutes, seconds, and milliseconds collapse to one duration."""

from __future__ import annotations


def parts_to_ms(hours: int = 0, minutes: int = 0, seconds: int = 0, milliseconds: int = 0) -> int:
    if min(hours, minutes, seconds, milliseconds) < 0:
        raise ValueError("Time parts cannot be negative")
    if hours > 48 or minutes > 59 or seconds > 59 or milliseconds > 999:
        raise ValueError("Time part out of range")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def ms_to_parts(total_ms: int) -> dict[str, int]:
    if total_ms < 0:
        raise ValueError("Duration cannot be negative")
    milliseconds = total_ms % 1000
    total_seconds = total_ms // 1000
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
        "milliseconds": milliseconds,
    }


def format_duration(ms: float) -> str:
    total = max(0, int(ms // 1000))
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
