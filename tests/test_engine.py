import tempfile
import time
import unittest
from pathlib import Path

from autoclicker.controller import BusyAutomation, Controller, EmergencyLatched
from autoclicker.core.engine import ClickEngine
from autoclicker.core.models import ClickJob, SafetyPolicy
from autoclicker.core.safety import ValidationError, validate_job
from autoclicker.core.timing import ms_to_parts, parts_to_ms
from autoclicker.platform.input_backend import FakeBackend
from autoclicker.platform.screen import ArrayScreen
from autoclicker.storage.database import Database
import numpy as np


def fast_policy() -> SafetyPolicy:
    return SafetyPolicy(max_cps=50, confirm_above_cps=50, max_session_ms=60_000)


class TimingTests(unittest.TestCase):
    def test_parts_round_trip(self):
        total = parts_to_ms(1, 2, 3, 4)
        self.assertEqual(total, 3_723_004)
        self.assertEqual(ms_to_parts(total), {
            "hours": 1, "minutes": 2, "seconds": 3, "milliseconds": 4
        })

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            parts_to_ms(0, 0, -1, 0)


class EngineTests(unittest.TestCase):
    def test_count_button_and_stop(self):
        backend = FakeBackend()
        engine = ClickEngine(backend, fast_policy())
        job = ClickJob(
            button="right",
            interval_ms=30,
            repeat_mode="count",
            repeat_count=4,
            user_confirmed=True,
        )
        engine.start(job, "right-hand")
        engine.join(3)
        clicks = [event for event in backend.events if event[0] == "click"]
        self.assertEqual(len(clicks), 4)
        self.assertTrue(all(event[1] == "right" for event in clicks))
        self.assertEqual(engine.stats.cycles, 4)
        self.assertEqual(engine.stats.message, "completed")
        self.assertFalse(engine.is_running)

    def test_double_click_counts_two(self):
        backend = FakeBackend()
        engine = ClickEngine(backend, fast_policy())
        engine.start(ClickJob(click_type="double", interval_ms=80, repeat_count=2, user_confirmed=True))
        engine.join(3)
        self.assertEqual(engine.stats.clicks, 4)
        self.assertEqual(engine.stats.cycles, 2)

    def test_fixed_and_multi_positions(self):
        backend = FakeBackend()
        engine = ClickEngine(backend, fast_policy())
        engine.start(ClickJob(
            interval_ms=25,
            repeat_count=1,
            position_mode="fixed",
            x=11,
            y=22,
            user_confirmed=True,
        ))
        engine.join(2)
        self.assertIn(("move", (11, 22)), backend.events)
        backend.events.clear()
        engine.start(ClickJob(
            interval_ms=25,
            repeat_count=4,
            position_mode="multi",
            points=[[1, 2], [3, 4]],
            point_order="sequential",
            user_confirmed=True,
        ))
        engine.join(3)
        moves = [event[1] for event in backend.events if event[0] == "move"]
        self.assertEqual(moves, [(1, 2), (3, 4), (1, 2), (3, 4)])

    def test_cursor_does_not_move(self):
        backend = FakeBackend(cursor=(9, 8))
        engine = ClickEngine(backend, fast_policy())
        engine.start(ClickJob(interval_ms=25, repeat_count=2, position_mode="cursor", user_confirmed=True))
        engine.join(2)
        self.assertFalse(any(event[0] == "move" for event in backend.events))
        self.assertTrue(all(event[2] == (9, 8) for event in backend.events if event[0] == "click"))

    def test_pause_resume_and_manual_stop(self):
        backend = FakeBackend()
        engine = ClickEngine(backend, fast_policy())
        engine.start(ClickJob(interval_ms=40, repeat_mode="infinite", user_confirmed=True))
        time.sleep(0.12)
        engine.pause()
        held = engine.stats.clicks
        time.sleep(0.15)
        self.assertEqual(engine.stats.state, "paused")
        self.assertEqual(engine.stats.clicks, held)
        engine.resume()
        time.sleep(0.12)
        engine.stop()
        engine.join(2)
        self.assertGreater(engine.stats.clicks, held)
        self.assertEqual(engine.stats.message, "stopped")
        self.assertFalse(engine.is_running)

    def test_session_limit(self):
        backend = FakeBackend()
        policy = fast_policy()
        policy.max_session_ms = 120
        engine = ClickEngine(backend, policy)
        engine.start(ClickJob(interval_ms=30, repeat_mode="infinite", user_confirmed=True))
        engine.join(2)
        self.assertEqual(engine.stats.message, "session_limit")
        self.assertFalse(engine.is_running)

    def test_duplicate_worker_rejected(self):
        engine = ClickEngine(FakeBackend(), fast_policy())
        job = ClickJob(interval_ms=80, repeat_mode="infinite", user_confirmed=True)
        engine.start(job)
        with self.assertRaises(Exception):
            engine.start(job)
        engine.stop()
        engine.join(2)

    def test_validation_blocks_fast_and_unconfirmed(self):
        policy = SafetyPolicy()
        errors = validate_job(ClickJob(interval_ms=5, repeat_count=10), policy)
        self.assertTrue(any("at least" in error for error in errors))
        fast = ClickJob(interval_ms=40, repeat_mode="infinite")
        errors = validate_job(fast, policy)
        self.assertTrue(any("confirmation" in error or "exceeds" in error for error in errors))
        fast.user_confirmed = True
        fast.interval_ms = 1000
        fast.repeat_mode = "count"
        fast.repeat_count = 2
        self.assertEqual(validate_job(fast, policy), [])


class ControllerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db = Database(Path(self.tmp.name) / "t.db")
        self.controller = Controller(
            db,
            backend=FakeBackend(),
            screen=ArrayScreen(np.zeros((8, 8, 3), dtype=np.uint8)),
            enable_hooks=False,
        )
        self.controller.update_safety(fast_policy())

    def tearDown(self):
        self.controller.shutdown()
        self.tmp.cleanup()

    def test_emergency_latch_and_shutdown(self):
        self.controller.start_job(
            ClickJob(interval_ms=40, repeat_mode="infinite", user_confirmed=True),
            "live",
        )
        time.sleep(0.08)
        self.controller.emergency_stop()
        self.controller.engine.join(2)
        self.assertTrue(self.controller.emergency_latched)
        with self.assertRaises(EmergencyLatched):
            self.controller.start_job(ClickJob(interval_ms=1000, repeat_count=1, user_confirmed=True))
        self.controller.clear_emergency()
        self.controller.start_job(ClickJob(interval_ms=40, repeat_count=2, user_confirmed=True), "after")
        with self.assertRaises(BusyAutomation):
            self.controller.start_job(ClickJob(interval_ms=40, repeat_count=2, user_confirmed=True))
        self.controller.engine.join(2)
        self.controller.clear_tasks()
        self.assertFalse(self.controller.engine.is_running)

    def test_rejects_bad_job_without_clicking(self):
        with self.assertRaises(ValidationError):
            self.controller.start_job(ClickJob(interval_ms=1, repeat_count=3, user_confirmed=True))
        self.assertEqual(self.controller.backend.events, [])


if __name__ == "__main__":
    unittest.main()
