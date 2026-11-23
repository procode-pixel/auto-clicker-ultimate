"""Macro list, recorder, and action editor."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from autoclicker.core.macro import (
    delete_action,
    duplicate_action,
    insert_delay,
    reorder_action,
    update_action,
)
from autoclicker.core.models import Macro, MacroAction, new_id
from autoclicker.core.safety import ValidationError


class MacroPage(QWidget):
    def __init__(self, controller, tr, notify):
        super().__init__()
        self.controller = controller
        self.tr = tr
        self.notify = notify
        self.current: Macro | None = None
        root = QHBoxLayout(self)
        left = QVBoxLayout()
        self.library = QListWidget()
        self.library.currentRowChanged.connect(self._select)
        left.addWidget(self.library)
        self.name = QLineEdit()
        left.addWidget(self.name)
        record = QPushButton("Record")
        record.setToolTip("Records mouse and keyboard until you press Stop recording.")
        record.clicked.connect(self._record)
        self.record_button = record
        left.addWidget(record)
        save = QPushButton(tr("save"))
        save.clicked.connect(self._save)
        left.addWidget(save)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        self.actions = QListWidget()
        right.addWidget(self.actions)
        controls = QHBoxLayout()
        for label, slot in (
            ("Delete", self._delete),
            ("Duplicate", self._duplicate),
            ("Up", lambda: self._reorder(-1)),
            ("Down", lambda: self._reorder(1)),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            controls.addWidget(button)
        right.addLayout(controls)
        delay_row = QHBoxLayout()
        self.delay_ms = QSpinBox()
        self.delay_ms.setRange(10, 60_000)
        self.delay_ms.setValue(200)
        add_delay = QPushButton("Insert delay")
        add_delay.clicked.connect(self._delay)
        delay_row.addWidget(QLabel("ms"))
        delay_row.addWidget(self.delay_ms)
        delay_row.addWidget(add_delay)
        right.addLayout(delay_row)
        play_row = QHBoxLayout()
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.25, 5.0)
        self.speed.setSingleStep(0.25)
        self.speed.setValue(float(controller.db.get_setting("playback_speed") or 1))
        self.repeat = QSpinBox()
        self.repeat.setRange(1, 10_000)
        self.repeat.setValue(1)
        play = QPushButton("Play")
        play.setObjectName("Primary")
        play.clicked.connect(self._play)
        play_row.addWidget(QLabel("Speed"))
        play_row.addWidget(self.speed)
        play_row.addWidget(QLabel("Repeat"))
        play_row.addWidget(self.repeat)
        play_row.addWidget(play)
        right.addLayout(play_row)
        root.addLayout(right, 2)
        self.reload()

    def reload(self) -> None:
        self.library.clear()
        self._items = self.controller.db.macros()
        for macro in self._items:
            self.library.addItem(macro.name)
        if self._items:
            self.library.setCurrentRow(0)

    def _select(self, row: int) -> None:
        if row < 0 or row >= len(self._items):
            return
        self.current = self._items[row]
        self.name.setText(self.current.name)
        self.speed.setValue(self.current.speed)
        self.repeat.setValue(self.current.repeat)
        self._paint()

    def _paint(self) -> None:
        self.actions.clear()
        if not self.current:
            return
        for action in self.current.actions:
            detail = " ".join(f"{key}={value}" for key, value in action.params.items() if key != "actions")
            self.actions.addItem(f"{action.t:>6} ms  {action.type}  {detail}")

    def _mutate(self, actions: list[MacroAction]) -> None:
        if self.current is None:
            return
        self.current.actions = actions
        self._paint()

    def _delete(self) -> None:
        if self.current is None:
            return
        row = self.actions.currentRow()
        if row >= 0:
            self._mutate(delete_action(self.current.actions, row))

    def _duplicate(self) -> None:
        if self.current is None:
            return
        row = self.actions.currentRow()
        if row >= 0:
            self._mutate(duplicate_action(self.current.actions, row))

    def _reorder(self, delta: int) -> None:
        if self.current is None:
            return
        row = self.actions.currentRow()
        target = row + delta
        if row >= 0 and 0 <= target < len(self.current.actions):
            self._mutate(reorder_action(self.current.actions, row, target))
            self.actions.setCurrentRow(target)

    def _delay(self) -> None:
        if self.current is None:
            self.notify("Select a macro first")
            return
        index = self.actions.currentRow()
        if index < 0:
            index = len(self.current.actions)
        self._mutate(insert_delay(self.current.actions, index, self.delay_ms.value()))

    def _record(self) -> None:
        if not self.controller.recorder.recording:
            problem = self.controller.begin_recording()
            self.record_button.setText("Stop recording")
            self.notify(problem or "Recording. Stop when you are finished.")
            return
        macro = self.controller.finish_recording(self.name.text().strip() or "Recorded macro")
        self.record_button.setText("Record")
        if not macro.actions:
            self.notify("Nothing was recorded. On this system a global listener may be unavailable.")
            return
        self.controller.db.save_macro(macro)
        self.notify(f"Saved {len(macro.actions)} actions")
        self.reload()

    def _save(self) -> None:
        if self.current is None:
            self.current = Macro(id=new_id(), name=self.name.text().strip() or "Macro", actions=[])
        self.current.name = self.name.text().strip() or "Macro"
        self.current.speed = self.speed.value()
        self.current.repeat = self.repeat.value()
        try:
            from autoclicker.core.macro import validate_macro

            errors = validate_macro(self.current, self.controller.policy)
            if errors:
                raise ValidationError(errors)
        except ValidationError as exc:
            self.notify(str(exc))
            return
        self.controller.db.save_macro(self.current)
        self.controller.db.set_setting("playback_speed", str(self.speed.value()))
        self.notify("Macro saved")
        self.reload()

    def _play(self) -> None:
        self._save()
        if self.current is None:
            return
        try:
            self.controller.start_macro(self.current)
            self.notify("Macro playing")
        except Exception as exc:  # noqa: BLE001
            self.notify(str(exc))

    def edit_selected_param(self, key: str, value) -> None:
        if self.current is None:
            return
        row = self.actions.currentRow()
        if row >= 0:
            self._mutate(update_action(self.current.actions, row, **{key: value}))
