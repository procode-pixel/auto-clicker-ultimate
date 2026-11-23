"""Pixel detection, image recognition, and the step builder."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from autoclicker.core.models import Workflow, new_id
from autoclicker.core.recognition import find_template, pixel_matches
from autoclicker.core.workflow import validate_workflow
from autoclicker.platform.screen import create_screen


class SmartPage(QWidget):
    def __init__(self, controller, tr, notify):
        super().__init__()
        self.controller = controller
        self.tr = tr
        self.notify = notify
        self.template_id: str | None = None
        root = QVBoxLayout(self)
        self.capture = QCheckBox("Allow screen capture while a recognition step is running")
        self.capture.stateChanged.connect(self._toggle_capture)
        root.addWidget(self.capture)
        self.capture_state = QLabel(tr("capture_off"))
        self.capture_state.setObjectName("Muted")
        root.addWidget(self.capture_state)
        form = QFormLayout()
        self.px = QSpinBox()
        self.py = QSpinBox()
        for box in (self.px, self.py):
            box.setRange(-32_000, 32_000)
        self.color = QLineEdit("10,20,30")
        self.tolerance = QSpinBox()
        self.tolerance.setRange(0, 255)
        self.tolerance.setValue(12)
        self.region = QLineEdit("")
        self.region.setPlaceholderText("x,y,width,height — leave empty for the full screen")
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.10, 0.99)
        self.confidence.setSingleStep(0.05)
        self.confidence.setValue(0.85)
        form.addRow("Pixel X", self.px)
        form.addRow("Pixel Y", self.py)
        form.addRow("Color R,G,B", self.color)
        form.addRow("Tolerance", self.tolerance)
        form.addRow("Region", self.region)
        form.addRow("Image confidence", self.confidence)
        root.addLayout(form)
        row = QHBoxLayout()
        test_pixel = QPushButton("Test pixel")
        test_pixel.clicked.connect(self._test_pixel)
        load = QPushButton("Load reference image")
        load.clicked.connect(self._load)
        test_image = QPushButton("Test image")
        test_image.clicked.connect(self._test_image)
        for button in (test_pixel, load, test_image):
            row.addWidget(button)
        root.addLayout(row)
        self.result = QLabel("No detection has run.")
        self.result.setWordWrap(True)
        root.addWidget(self.result)
        root.addStretch(1)

    def _toggle_capture(self) -> None:
        self.controller.capture_enabled = self.capture.isChecked()
        self.capture_state.setText(
            self.tr("capture_on") if self.controller.capture_enabled else self.tr("capture_off")
        )

    def _parsed_region(self):
        text = self.region.text().strip()
        if not text:
            return None
        parts = [int(part.strip()) for part in text.split(",")]
        if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
            raise ValueError("Region must be x, y, width, height")
        return tuple(parts)

    def _color(self) -> tuple[int, int, int]:
        parts = [int(part.strip()) for part in self.color.text().split(",")]
        if len(parts) != 3 or any(not 0 <= part <= 255 for part in parts):
            raise ValueError("Color must be R,G,B from 0 to 255")
        return parts[0], parts[1], parts[2]

    def _grab(self):
        if not self.controller.capture_enabled:
            raise RuntimeError("Turn on screen capture first. Nothing is captured until you do.")
        screen = create_screen()
        return screen.grab(self._parsed_region())

    def _test_pixel(self) -> None:
        try:
            image = self._grab()
            region = self._parsed_region()
            x, y = self.px.value(), self.py.value()
            if region:
                x -= region[0]
                y -= region[1]
            matched = pixel_matches(image, x, y, self._color(), self.tolerance.value())
            self.result.setText("Pixel matches." if matched else "Pixel does not match.")
        except Exception as exc:  # noqa: BLE001
            self.result.setText(str(exc))

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Reference image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        try:
            data = open(path, "rb").read()
            self.template_id = self.controller.store_template(path.split("/")[-1].split("\\")[-1], data)
            self.controller.capture_enabled = True
            self.capture.setChecked(True)
            self.result.setText(f"Stored reference image {self.template_id}")
        except Exception as exc:  # noqa: BLE001
            self.result.setText(str(exc))

    def _test_image(self) -> None:
        try:
            if not self.template_id:
                raise RuntimeError("Load a reference image first.")
            blob = self.controller.db.template_png(self.template_id)
            if not blob:
                raise RuntimeError("Reference image is missing.")
            from autoclicker.controller import _decode_image

            needle = _decode_image(blob)
            haystack = self._grab()
            region = self._parsed_region()
            offset = (region[0], region[1]) if region else (0, 0)
            match = find_template(haystack, needle, self.confidence.value(), offset=offset)
            if match is None:
                self.result.setText("No match at that confidence.")
            else:
                self.result.setText(
                    f"Match at {match.x}, {match.y}  confidence {match.confidence:.3f}"
                )
        except Exception as exc:  # noqa: BLE001
            self.result.setText(str(exc))


class BuilderPage(QWidget):
    def __init__(self, controller, tr, notify):
        super().__init__()
        self.controller = controller
        self.notify = notify
        self.steps: list[dict] = []
        root = QVBoxLayout(self)
        self.name = QLineEdit("New workflow")
        root.addWidget(self.name)
        self.list = QListWidget()
        root.addWidget(self.list)
        adders = QHBoxLayout()
        catalog = [
            ("Click", {"type": "click", "button": "left", "times": 1}),
            ("Move", {"type": "move", "x": 0, "y": 0}),
            ("Key", {"type": "key", "key": "esc"}),
            ("Wait", {"type": "wait", "ms": 200}),
            ("Repeat", {"type": "repeat", "count": 2, "steps": [{"type": "wait", "ms": 50}]}),
            ("Pixel if", {
                "type": "if",
                "when": {"kind": "pixel", "x": 0, "y": 0, "color": [0, 0, 0], "tolerance": 10},
                "then": [{"type": "wait", "ms": 20}],
                "else": [],
            }),
            ("Stop", {"type": "stop"}),
        ]
        for label, template in catalog:
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, body=template: self._add(body))
            adders.addWidget(button)
        root.addLayout(adders)
        tools = QHBoxLayout()
        for label, slot in (
            ("Remove", self._remove),
            ("Up", lambda: self._shift(-1)),
            ("Down", lambda: self._shift(1)),
            ("Validate", self._validate),
            ("Run", self._run),
            ("Save", self._save),
        ):
            button = QPushButton(label)
            if label == "Run":
                button.setObjectName("Primary")
            button.clicked.connect(slot)
            tools.addWidget(button)
        root.addLayout(tools)
        self.status = QLabel("Add steps, then validate. Repeats must contain a wait.")
        self.status.setWordWrap(True)
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

    def _paint(self) -> None:
        self.list.clear()
        for step in self.steps:
            self.list.addItem(json.dumps(step, ensure_ascii=False))

    def _add(self, template: dict) -> None:
        step = json.loads(json.dumps(template))
        step["id"] = new_id()
        self.steps.append(step)
        self._paint()

    def _remove(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self.steps.pop(row)
            self._paint()

    def _shift(self, delta: int) -> None:
        row = self.list.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < len(self.steps):
            return
        self.steps[row], self.steps[target] = self.steps[target], self.steps[row]
        self._paint()
        self.list.setCurrentRow(target)

    def _validate(self) -> bool:
        errors = validate_workflow(self.steps, self.controller.policy)
        self.status.setText("Workflow is valid." if not errors else "\n".join(errors))
        return not errors

    def _save(self) -> None:
        if not self._validate():
            return
        workflow = Workflow(id=new_id(), name=self.name.text().strip() or "Workflow", steps=self.steps)
        self.controller.db.save_workflow(workflow)
        self.notify("Workflow saved")

    def _run(self) -> None:
        if not self._validate():
            return
        workflow = Workflow(id=new_id(), name=self.name.text().strip() or "Workflow", steps=self.steps)
        self.controller.db.save_workflow(workflow)
        try:
            self.controller.start_workflow(workflow)
            self.notify("Workflow started")
        except Exception as exc:  # noqa: BLE001
            self.notify(str(exc))
