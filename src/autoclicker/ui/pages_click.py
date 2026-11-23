"""Dashboard, click engine, and position list."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from autoclicker.core.models import ClickJob, new_id, Profile
from autoclicker.core.timing import format_duration, ms_to_parts, parts_to_ms
from autoclicker.ui.picker import PointPicker


def _card(title: str) -> tuple[QWidget, QVBoxLayout]:
    frame = QWidget()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    heading = QLabel(title)
    heading.setObjectName("Brand")
    layout.addWidget(heading)
    return frame, layout


class DashboardPage(QWidget):
    def __init__(self, controller, tr):
        super().__init__()
        self.controller = controller
        self.tr = tr
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.value_state = self._stat(grid, 0, 0, tr("idle"))
        self.value_clicks = self._stat(grid, 0, 1, "0")
        self.value_duration = self._stat(grid, 0, 2, "00:00")
        self.value_speed = self._stat(grid, 1, 0, "0.0")
        self.value_profile = self._stat(grid, 1, 1, "—")
        root.addLayout(grid)
        activity_card, activity_layout = _card(tr("activity"))
        self.activity = QLabel(tr("empty_activity"))
        self.activity.setWordWrap(True)
        self.activity.setObjectName("Muted")
        activity_layout.addWidget(self.activity)
        root.addWidget(activity_card)
        root.addStretch(1)
        self.state_caption = grid.itemAtPosition(0, 0).widget()

    def _stat(self, grid: QGridLayout, row: int, col: int, value: str) -> QLabel:
        frame, layout = _card("")
        caption = QLabel("")
        caption.setObjectName("Muted")
        number = QLabel(value)
        number.setObjectName("StatValue")
        layout.insertWidget(0, caption)
        layout.addWidget(number)
        grid.addWidget(frame, row, col)
        number._caption = caption  # type: ignore[attr-defined]
        return number

    def refresh(self) -> None:
        stats = self.controller.snapshot()
        labels = {
            "idle": self.tr("idle"),
            "running": self.tr("running"),
            "paused": self.tr("paused"),
            "armed": self.tr("armed"),
        }
        self.value_state.setText(labels.get(stats.state, stats.state))
        self.value_state._caption.setText(self.tr("dashboard"))  # type: ignore[attr-defined]
        self.value_clicks.setText(str(stats.clicks))
        self.value_clicks._caption.setText(self.tr("clicks"))  # type: ignore[attr-defined]
        self.value_duration.setText(format_duration(stats.elapsed_ms))
        self.value_duration._caption.setText(self.tr("duration"))  # type: ignore[attr-defined]
        self.value_speed.setText(f"{stats.cps:.1f}/s")
        self.value_speed._caption.setText(self.tr("speed"))  # type: ignore[attr-defined]
        self.value_profile.setText(stats.profile_name or "—")
        self.value_profile._caption.setText(self.tr("profile"))  # type: ignore[attr-defined]
        rows = self.controller.db.activity(8)
        if not rows:
            self.activity.setText(self.tr("empty_activity"))
        else:
            self.activity.setText("\n".join(f"{row['ts']}  {row['message']}" for row in rows))


class ClickerPage(QWidget):
    def __init__(self, controller, tr, notify):
        super().__init__()
        self.controller = controller
        self.tr = tr
        self.notify = notify
        self.points: list[list[int]] = []
        self.point_order = "sequential"
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.button = QComboBox()
        self.button.addItems(["left", "right", "middle"])
        self.click_type = QComboBox()
        self.click_type.addItems(["single", "double", "sequence"])
        self.sequence = QLineEdit("left:1")
        self.sequence.setToolTip("Example: left:1, right:1")
        self.mode = QComboBox()
        self.mode.addItems(["fixed", "random"])
        self.hours, self.minutes, self.seconds, self.millis = (
            self._spin(48),
            self._spin(59),
            self._spin(59),
            self._spin(999),
        )
        self.millis.setValue(100)
        self.rand_min = self._spin(60_000)
        self.rand_min.setValue(80)
        self.rand_max = self._spin(60_000)
        self.rand_max.setValue(180)
        self.repeat = QComboBox()
        self.repeat.addItems(["count", "infinite", "duration"])
        self.count = self._spin(1_000_000)
        self.count.setValue(10)
        self.dur_s = self._spin(86_400)
        self.dur_s.setValue(30)
        self.delay_ms = self._spin(86_400_000)
        self.schedule_on = QCheckBox("Start at a scheduled local time")
        self.schedule = QDateTimeEdit()
        self.schedule.setCalendarPopup(True)
        self.position = QComboBox()
        self.position.addItems(["cursor", "fixed", "multi"])
        self.x = self._spin(32_000)
        self.y = self._spin(32_000)
        self.x.setMinimum(-32_000)
        self.y.setMinimum(-32_000)
        self.confirm = QCheckBox(tr("confirm"))
        self.profile_name = QLineEdit("Manual")
        interval = QHBoxLayout()
        for label, widget in (
            ("h", self.hours),
            ("m", self.minutes),
            ("s", self.seconds),
            ("ms", self.millis),
        ):
            interval.addWidget(QLabel(label))
            interval.addWidget(widget)
        form.addRow("Button", self.button)
        form.addRow("Click", self.click_type)
        form.addRow("Sequence", self.sequence)
        form.addRow("Interval", interval)
        form.addRow("Interval mode", self.mode)
        form.addRow("Random min ms", self.rand_min)
        form.addRow("Random max ms", self.rand_max)
        form.addRow("Repeat", self.repeat)
        form.addRow("Count", self.count)
        form.addRow("Duration seconds", self.dur_s)
        form.addRow("Start delay ms", self.delay_ms)
        form.addRow(self.schedule_on, self.schedule)
        form.addRow("Position", self.position)
        form.addRow("X", self.x)
        form.addRow("Y", self.y)
        form.addRow("Profile name", self.profile_name)
        form.addRow(self.confirm)
        root.addLayout(form)
        actions = QHBoxLayout()
        save = QPushButton(tr("save"))
        save.clicked.connect(self._save)
        actions.addWidget(save)
        actions.addStretch(1)
        root.addLayout(actions)
        root.addStretch(1)

    def _spin(self, upper: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(0, upper)
        return box

    def build_job(self) -> ClickJob:
        sequence = []
        if self.click_type.currentText() == "sequence":
            for chunk in self.sequence.text().split(","):
                if not chunk.strip():
                    continue
                button, _, times = chunk.strip().partition(":")
                sequence.append({"button": button.strip(), "times": int(times or 1)})
        epoch = None
        if self.schedule_on.isChecked():
            epoch = self.schedule.dateTime().toSecsSinceEpoch()
        return ClickJob(
            button=self.button.currentText(),
            click_type=self.click_type.currentText(),
            sequence=sequence,
            interval_ms=parts_to_ms(
                self.hours.value(), self.minutes.value(), self.seconds.value(), self.millis.value()
            ),
            interval_mode=self.mode.currentText(),
            random_min_ms=self.rand_min.value(),
            random_max_ms=self.rand_max.value(),
            repeat_mode=self.repeat.currentText(),
            repeat_count=self.count.value(),
            duration_ms=self.dur_s.value() * 1000,
            start_delay_ms=self.delay_ms.value(),
            scheduled_epoch=epoch,
            position_mode=self.position.currentText(),
            x=self.x.value(),
            y=self.y.value(),
            points=self.points,
            point_order=self.point_order,
            user_confirmed=self.confirm.isChecked(),
        )

    def load_job(self, job: ClickJob, name: str) -> None:
        self.button.setCurrentText(job.button)
        self.click_type.setCurrentText(job.click_type)
        self.mode.setCurrentText(job.interval_mode)
        parts = ms_to_parts(job.interval_ms)
        self.hours.setValue(parts["hours"])
        self.minutes.setValue(parts["minutes"])
        self.seconds.setValue(parts["seconds"])
        self.millis.setValue(parts["milliseconds"])
        self.rand_min.setValue(job.random_min_ms)
        self.rand_max.setValue(job.random_max_ms)
        self.repeat.setCurrentText(job.repeat_mode)
        self.count.setValue(job.repeat_count)
        self.dur_s.setValue(max(1, job.duration_ms // 1000))
        self.delay_ms.setValue(job.start_delay_ms)
        self.position.setCurrentText(job.position_mode)
        self.x.setValue(job.x)
        self.y.setValue(job.y)
        self.points = [list(point) for point in job.points]
        self.point_order = job.point_order
        self.profile_name.setText(name)
        self.confirm.setChecked(job.user_confirmed)
        if job.sequence:
            self.sequence.setText(
                ", ".join(f"{step.get('button', 'left')}:{step.get('times', 1)}" for step in job.sequence)
            )

    def _save(self) -> None:
        try:
            job = self.build_job()
            profile = Profile(id=new_id(), name=self.profile_name.text().strip() or "Manual", job=job)
            self.controller.db.save_profile(profile)
            self.notify("Profile saved")
        except Exception as exc:  # noqa: BLE001 - show the message
            self.notify(str(exc))


class PositionsPage(QWidget):
    def __init__(self, controller, clicker: ClickerPage, tr, notify):
        super().__init__()
        self.controller = controller
        self.clicker = clicker
        self.notify = notify
        root = QVBoxLayout(self)
        self.live = QLabel("Cursor: —")
        self.live.setObjectName("Muted")
        root.addWidget(self.live)
        self.list = QListWidget()
        root.addWidget(self.list)
        row = QHBoxLayout()
        for label, slot in (
            ("Add cursor", self._add_cursor),
            ("Pick on screen", self._pick),
            ("Remove", self._remove),
            ("Move up", lambda: self._move(-1)),
            ("Move down", lambda: self._move(1)),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            row.addWidget(button)
        root.addLayout(row)
        self.order = QComboBox()
        self.order.addItems(["sequential", "random"])
        root.addWidget(self.order)
        self._picker: PointPicker | None = None

    def refresh_cursor(self) -> None:
        x, y = self.controller.cursor()
        self.live.setText(f"Cursor: {x}, {y}")

    def sync_from_clicker(self) -> None:
        self.list.clear()
        for point in self.clicker.points:
            self.list.addItem(f"{point[0]}, {point[1]}")

    def _write(self) -> None:
        points = []
        for index in range(self.list.count()):
            text = self.list.item(index).text()
            x, y = text.split(",")
            points.append([int(x), int(y)])
        self.clicker.points = points
        self.clicker.point_order = self.order.currentText()

    def _add_cursor(self) -> None:
        x, y = self.controller.cursor()
        self.list.addItem(f"{x}, {y}")
        self._write()

    def _pick(self) -> None:
        self._picker = PointPicker()
        self._picker.picked.connect(self._picked)
        self._picker.showFullScreen()

    def _picked(self, x: int, y: int) -> None:
        self.list.addItem(f"{x}, {y}")
        self._write()
        self.notify(f"Saved position {x}, {y}")

    def _remove(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self.list.takeItem(row)
            self._write()

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(target, item)
        self.list.setCurrentRow(target)
        self._write()
