"""Background click engine. The UI thread never clicks and never waits on the timer."""

from __future__ import annotations

import random
import threading
import time
from typing import Callable

from autoclicker.core.models import ClickJob, EngineStats, SafetyPolicy
from autoclicker.core.safety import ValidationError, validate_job


class EngineBusyError(RuntimeError):
    pass


Listener = Callable[[EngineStats], None]


class ClickEngine:
    def __init__(
        self,
        backend,
        policy: SafetyPolicy,
        *,
        sleeper: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
        wall_clock: Callable[[], float] | None = None,
    ):
        self.backend = backend
        self.policy = policy
        self._sleep = sleeper or time.sleep
        self._clock = clock or time.perf_counter
        self._wall = wall_clock or time.time
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.stats = EngineStats()
        self.listeners: list[Listener] = []
        self._rng = random.Random()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def set_policy(self, policy: SafetyPolicy) -> None:
        self.policy = policy

    def start(self, job: ClickJob, profile_name: str = "") -> None:
        errors = validate_job(job, self.policy)
        if errors:
            raise ValidationError(errors)
        with self._lock:
            if self.is_running:
                raise EngineBusyError("A click worker is already running")
            self._stop.clear()
            self._pause.clear()
            self.stats = EngineStats(state="armed", profile_name=profile_name)
            self._emit()
            self._thread = threading.Thread(
                target=self._run,
                args=(job,),
                name="click-engine",
                daemon=True,
            )
            self._thread.start()

    def pause(self) -> None:
        if self.is_running and not self._pause.is_set():
            self._pause.set()
            self.stats.state = "paused"
            self._emit()

    def resume(self) -> None:
        if self.is_running and self._pause.is_set():
            self._pause.clear()
            self.stats.state = "running"
            self._emit()

    def stop(self) -> None:
        self._stop.set()
        self._pause.clear()

    def join(self, timeout: float = 3.0) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _emit(self) -> None:
        snapshot = EngineStats(**self.stats.to_dict())
        for listener in list(self.listeners):
            listener(snapshot)

    def _wait(self, ms: float) -> bool:
        remaining = max(0.0, ms) / 1000.0
        slice_s = 0.02
        while remaining > 0:
            if self._stop.is_set():
                return False
            if self._pause.is_set():
                self._sleep(slice_s)
                continue
            step = min(slice_s, remaining)
            self._sleep(step)
            remaining -= step
        return not self._stop.is_set()

    def _interval(self, job: ClickJob) -> int:
        if job.interval_mode == "random":
            return self._rng.randint(int(job.random_min_ms), int(job.random_max_ms))
        return int(job.interval_ms)

    def _position(self, job: ClickJob, index: int) -> tuple[int, int] | None:
        if job.position_mode == "cursor":
            return None
        if job.position_mode == "fixed":
            return int(job.x), int(job.y)
        points = job.points
        if job.point_order == "random":
            chosen = points[self._rng.randrange(len(points))]
        else:
            chosen = points[index % len(points)]
        return int(chosen[0]), int(chosen[1])

    def _perform(self, job: ClickJob, pos: tuple[int, int] | None) -> int:
        if pos is not None:
            self.backend.move(pos[0], pos[1])
        if job.click_type == "single":
            self.backend.click(job.button, 1)
            return 1
        if job.click_type == "double":
            self.backend.click(job.button, 2, 50)
            return 2
        total = 0
        for step in job.sequence:
            times = int(step.get("times", 1))
            self.backend.click(str(step["button"]), times, int(step.get("gap_ms") or 40))
            total += times
            gap = int(step.get("after_ms") or 0)
            if gap and not self._wait(gap):
                break
        return total

    def _run(self, job: ClickJob) -> None:
        started = self._clock()
        try:
            if job.scheduled_epoch is not None:
                delay_ms = (float(job.scheduled_epoch) - self._wall()) * 1000.0
                if delay_ms > 0 and not self._wait(delay_ms):
                    self._finish(started, "stopped")
                    return
            if job.start_delay_ms and not self._wait(job.start_delay_ms):
                self._finish(started, "stopped")
                return
            self.stats.state = "running"
            self._emit()
            index = 0
            while not self._stop.is_set():
                if self._pause.is_set():
                    if not self._wait(20):
                        break
                    continue
                elapsed_ms = (self._clock() - started) * 1000.0
                if elapsed_ms >= self.policy.max_session_ms:
                    self._finish(started, "session_limit")
                    return
                if job.repeat_mode == "duration" and elapsed_ms >= job.duration_ms:
                    break
                if job.repeat_mode == "count" and index >= job.repeat_count:
                    break
                physical = self._perform(job, self._position(job, index))
                index += 1
                elapsed_ms = (self._clock() - started) * 1000.0
                self.stats.clicks += physical
                self.stats.cycles = index
                self.stats.elapsed_ms = elapsed_ms
                self.stats.cps = self.stats.clicks / max(elapsed_ms / 1000.0, 0.001)
                self.stats.state = "paused" if self._pause.is_set() else "running"
                self._emit()
                if job.repeat_mode == "count" and index >= job.repeat_count:
                    break
                if job.repeat_mode == "duration" and elapsed_ms >= job.duration_ms:
                    break
                if not self._wait(self._interval(job)):
                    break
            reason = "stopped" if self._stop.is_set() else "completed"
            self._finish(started, reason)
        except Exception as exc:  # noqa: BLE001 — worker must not die silently
            self.stats.message = str(exc)
            self._finish(started, "error")

    def _finish(self, started: float, reason: str) -> None:
        self.stats.elapsed_ms = (self._clock() - started) * 1000.0
        self.stats.state = "idle"
        self.stats.message = reason
        if self.stats.elapsed_ms > 0:
            self.stats.cps = self.stats.clicks / max(self.stats.elapsed_ms / 1000.0, 0.001)
        self._emit()
