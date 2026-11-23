import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from autoclicker.controller import Controller
from autoclicker.core.hotkeys import find_conflicts, normalize_combo
from autoclicker.core.macro import (
    MacroPlayer,
    MacroRecorder,
    delete_action,
    duplicate_action,
    insert_delay,
    reorder_action,
    validate_macro,
    wrap_loop,
)
from autoclicker.core.models import Macro, MacroAction, SafetyPolicy, new_id
from autoclicker.core.recognition import find_template, pixel_matches
from autoclicker.core.safety import ValidationError
from autoclicker.core.workflow import WorkflowRunner, validate_workflow
from autoclicker.platform.input_backend import FakeBackend
from autoclicker.platform.screen import ArrayScreen
from autoclicker.storage.database import Database
from autoclicker.storage.exchange import ImportRejected, export_bundle, load_document


POLICY = SafetyPolicy(max_cps=40, confirm_above_cps=40)


class MacroTests(unittest.TestCase):
    def test_editor_and_recorder_throttle(self):
        recorder = MacroRecorder()
        recorder.start()
        recorder.add("move", x=1, y=1)
        recorder.add("move", x=2, y=2)
        recorder.add("click", button="left", action="click", x=2, y=2)
        macro = recorder.stop("sample")
        self.assertEqual(len(macro.actions), 2)
        self.assertEqual(macro.actions[0].params["x"], 2)
        actions = duplicate_action(macro.actions, 1)
        self.assertEqual(len(actions), 3)
        actions = reorder_action(actions, 2, 0)
        actions = insert_delay(actions, 1, 25)
        actions = delete_action(actions, 1)
        self.assertTrue(all(action.type != "delay" or False for action in actions[:1]))
        looped = wrap_loop(
            [MacroAction("click", 0, {"button": "left"}), MacroAction("delay", 10, {"ms": 20})],
            0,
            1,
            3,
        )
        self.assertEqual(looped[0].type, "loop")
        bare = wrap_loop([MacroAction("click", 0, {"button": "left"}), MacroAction("click", 5, {"button": "left"})], 0, 1, 4)
        errors = validate_macro(Macro(id="1", name="loop", actions=bare), POLICY)
        self.assertTrue(any("delay" in error for error in errors))

    def test_playback_order_and_repeat(self):
        backend = FakeBackend()
        player = MacroPlayer(backend, POLICY)
        macro = Macro(
            id="m",
            name="play",
            speed=1,
            repeat=2,
            actions=[
                MacroAction("click", 0, {"button": "middle", "action": "click"}),
                MacroAction("delay", 0, {"ms": 20}),
                MacroAction("key", 20, {"key": "esc", "action": "tap"}),
            ],
        )
        player.start(macro)
        player.join(2)
        kinds = [event[0] for event in backend.events]
        self.assertEqual(kinds, ["click", "key_down", "key_up", "click", "key_down", "key_up"])
        self.assertEqual(player.message, "completed")

    def test_stop_during_playback(self):
        backend = FakeBackend()
        player = MacroPlayer(backend, POLICY)
        macro = Macro(
            id="m2",
            name="long",
            actions=[MacroAction("delay", 0, {"ms": 500}), MacroAction("click", 500, {"button": "left"})],
        )
        player.start(macro)
        player.stop()
        player.join(2)
        self.assertEqual(player.message, "stopped")
        self.assertFalse(any(event[0] == "click" for event in backend.events))

    def test_import_rejects_code(self):
        hostile = {
            "schema": "autoclicker.macro",
            "version": 1,
            "name": "nope",
            "actions": [{"type": "key", "key": "a", "exec": "print(1)"}],
        }
        with self.assertRaises(ImportRejected):
            load_document(json.dumps(hostile), POLICY)
        unknown = {"schema": "autoclicker.macro", "version": 1, "name": "x", "actions": [{"type": "shell"}]}
        with self.assertRaises(ImportRejected):
            load_document(json.dumps(unknown), POLICY)


class RecognitionTests(unittest.TestCase):
    def test_pixel_tolerance(self):
        image = np.zeros((6, 6, 3), dtype=np.uint8)
        image[2, 3] = (10, 20, 30)
        self.assertTrue(pixel_matches(image, 3, 2, (10, 20, 30), 0))
        self.assertTrue(pixel_matches(image, 3, 2, (12, 18, 34), 5))
        self.assertFalse(pixel_matches(image, 3, 2, (80, 20, 30), 5))
        self.assertFalse(pixel_matches(image, 0, 0, (10, 20, 30), 0))

    def test_template_found_and_missed(self):
        scene = np.zeros((40, 50, 3), dtype=np.uint8)
        scene[8:18, 12:22] = (20, 140, 90)
        scene[8:18, 12:22, 0] = np.arange(10)
        needle = scene[8:18, 12:22].copy()
        match = find_template(scene, needle, 0.9)
        self.assertIsNotNone(match)
        self.assertEqual((match.x, match.y), (12, 8))
        other = np.zeros((8, 8, 3), dtype=np.uint8)
        other[:, :, 0] = np.array([10, 200, 15, 220, 30, 180, 5, 240], dtype=np.uint8)
        other[:, :, 1] = np.array([200, 10, 180, 20, 160, 40, 140, 60], dtype=np.uint8)
        other[:, :, 2] = 90
        self.assertIsNone(find_template(scene, other, 0.9))
        self.assertIsNone(find_template(scene, np.full((8, 8, 3), 255, dtype=np.uint8), 0.9))


class WorkflowTests(unittest.TestCase):
    def test_pixel_condition_and_stop(self):
        image = np.zeros((8, 8, 3), dtype=np.uint8)
        image[1, 1] = (10, 20, 30)
        backend = FakeBackend()
        runner = WorkflowRunner(backend, POLICY, ArrayScreen(image))
        steps = [
            {"type": "wait", "ms": 20},
            {
                "type": "if",
                "when": {"kind": "pixel", "x": 1, "y": 1, "color": [10, 20, 30], "tolerance": 2},
                "then": [{"type": "click", "button": "left", "x": 4, "y": 5}],
                "else": [{"type": "stop"}],
            },
        ]
        self.assertEqual(runner.run_inline(steps), "completed")
        self.assertIn(("move", (4, 5)), backend.events)
        self.assertTrue(any(event[0] == "click" for event in backend.events))

    def test_image_click_and_endless_loop_rejected(self):
        scene = np.zeros((30, 30, 3), dtype=np.uint8)
        patch = np.zeros((7, 8, 3), dtype=np.uint8)
        patch[:, :, 1] = np.linspace(30, 220, 8, dtype=np.uint8)
        patch[:, :, 2] = 180
        scene[5:12, 6:14] = patch
        needle = scene[5:12, 6:14].copy()
        backend = FakeBackend()
        runner = WorkflowRunner(backend, POLICY, ArrayScreen(scene), templates={"mark": needle})
        reason = runner.run_inline([
            {
                "type": "image",
                "template_id": "mark",
                "confidence": 0.8,
                "on_found": "click_center",
            }
        ])
        self.assertEqual(reason, "completed")
        self.assertTrue(any(event[0] == "click" for event in backend.events))
        errors = validate_workflow(
            [{"type": "repeat", "count": 5, "steps": [{"type": "click", "button": "left"}]}],
            POLICY,
        )
        self.assertTrue(errors)
        with self.assertRaises(ValidationError):
            runner.run_inline([{"type": "repeat", "count": 3, "steps": [{"type": "key", "key": "a"}]}])

    def test_emergency_stops_workflow(self):
        backend = FakeBackend()
        runner = WorkflowRunner(backend, POLICY, ArrayScreen(np.zeros((4, 4, 3), dtype=np.uint8)))
        runner.start([{"type": "wait", "ms": 400}, {"type": "click", "button": "left"}])
        runner.stop()
        runner.join(2)
        self.assertEqual(runner.message, "stopped")
        self.assertFalse(any(event[0] == "click" for event in backend.events))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "app.db")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_profiles_default_duplicate_and_bundle(self):
        profiles = self.db.profiles()
        self.assertGreaterEqual(len(profiles), 3)
        self.assertTrue(any(profile.is_default for profile in profiles))
        first = profiles[0]
        copy = self.db.duplicate_profile(first.id, "Copy of gentle")
        self.assertNotEqual(copy.id, first.id)
        self.db.delete_profile(copy.id)
        self.assertIsNone(self.db.profile(copy.id))
        text = export_bundle(self.db.profiles(), self.db.macros(), self.db.workflows())
        loaded = load_document(text, POLICY)
        self.assertGreaterEqual(len(loaded["profiles"]), 3)
        self.assertGreaterEqual(len(loaded["macros"]), 1)

    def test_hotkeys_and_stats_export(self):
        conflicts = find_conflicts({"start": "f6", "stop": "f6", "emergency": "f12"})
        self.assertTrue(any("both" in item for item in conflicts))
        self.assertEqual(normalize_combo("Ctrl+Shift+F12"), "ctrl+shift+f12")
        clean = find_conflicts({
            "start": "f6", "pause": "f7", "resume": "f8", "stop": "f9",
            "emergency": "ctrl+shift+f12", "profile": "",
        })
        self.assertEqual(clean, [])
        self.db.add_session(
            profile_name="Gentle cursor click",
            kind="click",
            started_at="2026-01-01T00:00:00+00:00",
            clicks=10,
            duration_ms=10_000,
            reason="completed",
        )
        summary = self.db.analytics_summary()
        self.assertEqual(summary["clicks"], 10)
        self.assertEqual(summary["sessions"], 1)
        self.assertAlmostEqual(summary["average_cps"], 1.0)
        controller = Controller(
            self.db,
            backend=FakeBackend(),
            screen=ArrayScreen(np.zeros((4, 4, 3), dtype=np.uint8)),
            enable_hooks=False,
        )
        csv_text = controller.export_stats("csv")
        self.assertIn("Gentle cursor click", csv_text)
        self.assertIn("clicks", csv_text.splitlines()[0])
        payload = json.loads(controller.export_stats("json"))
        self.assertEqual(payload["schema"], "autoclicker.stats")
        buffer = io.BytesIO()
        Image.new("RGB", (12, 10), (1, 2, 3)).save(buffer, format="PNG")
        template_id = controller.store_template("sample.png", buffer.getvalue())
        self.assertIsNotNone(self.db.template_png(template_id))
        controller.shutdown()

    def test_malicious_profile_rejected(self):
        fast = {
            "schema": "autoclicker.profile",
            "version": 1,
            "id": new_id(),
            "name": "too fast",
            "job": {"interval_ms": 1, "repeat_count": 5, "user_confirmed": True},
        }
        with self.assertRaises(ImportRejected):
            load_document(json.dumps(fast), SafetyPolicy())


if __name__ == "__main__":
    unittest.main()
