"""Profiles, hotkeys, analytics, safety, and settings."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from autoclicker.core.hotkeys import DEFAULT_BINDINGS
from autoclicker.core.models import SafetyPolicy
from autoclicker.core.timing import format_duration
from autoclicker.ui.theme import ACCENTS


class ProfilesPage(QWidget):
    def __init__(self, controller, clicker, tr, notify):
        super().__init__()
        self.controller = controller
        self.clicker = clicker
        self.tr = tr
        self.notify = notify
        root = QVBoxLayout(self)
        self.list = QListWidget()
        root.addWidget(self.list)
        self.rename = QLineEdit()
        root.addWidget(self.rename)
        row = QHBoxLayout()
        for label, slot in (
            ("Load", self._load),
            (tr("duplicate"), self._duplicate),
            ("Set default", self._default),
            (tr("delete"), self._delete),
            (tr("export"), self._export),
            (tr("import"), self._import),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            row.addWidget(button)
        root.addLayout(row)
        self.reload()

    def reload(self) -> None:
        self._profiles = self.controller.db.profiles()
        self.list.clear()
        for profile in self._profiles:
            mark = " · default" if profile.is_default else ""
            self.list.addItem(f"{profile.name}{mark}")

    def _current(self):
        row = self.list.currentRow()
        if row < 0 or row >= len(self._profiles):
            return None
        return self._profiles[row]

    def _load(self) -> None:
        profile = self._current()
        if profile is None:
            return
        self.clicker.load_job(profile.job, profile.name)
        self.rename.setText(profile.name)
        self.notify(f"Loaded {profile.name}. Open Click engine to review it.")

    def _duplicate(self) -> None:
        profile = self._current()
        if profile is None:
            return
        name = self.rename.text().strip() or f"{profile.name} copy"
        self.controller.db.duplicate_profile(profile.id, name)
        self.reload()

    def _default(self) -> None:
        profile = self._current()
        if profile is None:
            return
        profile.is_default = True
        self.controller.db.save_profile(profile)
        self.reload()
        self.notify("Default profile updated")

    def _delete(self) -> None:
        profile = self._current()
        if profile is None:
            return
        self.controller.db.delete_profile(profile.id)
        self.reload()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export", "profiles.json", "JSON (*.json)")
        if not path:
            return
        text = self.controller.export_all()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.notify("Exported profiles, macros, and workflows")

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import", "", "JSON (*.json)")
        if not path:
            return
        try:
            text = open(path, encoding="utf-8").read()
            loaded = self.controller.import_text(text)
            self.reload()
            self.notify(
                f"Imported {len(loaded['profiles'])} profiles, {len(loaded['macros'])} macros"
            )
        except Exception as exc:  # noqa: BLE001
            self.notify(str(exc))


class HotkeysPage(QWidget):
    def __init__(self, controller, tr, notify, on_saved=None):
        super().__init__()
        self.controller = controller
        self.notify = notify
        self.on_saved = on_saved
        root = QFormLayout(self)
        current = controller.hotkey_map()
        self.fields: dict[str, QLineEdit] = {}
        labels = {
            "start": "Start default profile",
            "pause": "Pause",
            "resume": "Resume",
            "stop": "Stop",
            "emergency": "Emergency stop",
            "profile": "Start selected profile",
        }
        for key, label in labels.items():
            field = QLineEdit(current.get(key, DEFAULT_BINDINGS.get(key, "")))
            field.setPlaceholderText("Example: ctrl+shift+f6")
            self.fields[key] = field
            root.addRow(label, field)
        save = QPushButton(tr("save"))
        save.clicked.connect(self._save)
        root.addRow(save)

    def _save(self) -> None:
        bindings = {key: field.text().strip().lower() for key, field in self.fields.items()}
        conflicts = self.controller.set_hotkeys(bindings)
        if conflicts:
            self.notify(" ; ".join(conflicts))
        else:
            if self.on_saved:
                self.on_saved()
            self.notify("Shortcuts saved. They also work while the window is minimized when the system allows a global hook.")


class SessionChart(QWidget):
    """Bar chart of recent session click counts. Empty until a real session ends."""

    def __init__(self):
        super().__init__()
        self._values: list[int] = []
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, values: list[int]) -> None:
        self._values = [max(0, int(v)) for v in values][-24:]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(8, 8, -8, -22)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        if not self._values or max(self._values) == 0:
            painter.setPen(QColor(160, 168, 180))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No sessions to chart yet")
            painter.end()
            return
        peak = max(self._values)
        gap = 4
        count = len(self._values)
        width = max(4, (rect.width() - gap * (count - 1)) // count)
        accent = QColor(88, 166, 255)
        painter.setPen(Qt.PenStyle.NoPen)
        for index, value in enumerate(self._values):
            height = int(rect.height() * (value / peak))
            x = rect.left() + index * (width + gap)
            bar = rect.adjusted(0, rect.height() - height, 0, 0)
            bar.setLeft(x)
            bar.setWidth(width)
            painter.fillRect(bar, accent)
        painter.setPen(QPen(QColor(140, 148, 160)))
        painter.drawText(8, self.height() - 6, f"Last {count} sessions  ·  peak {peak} clicks")
        painter.end()


class AnalyticsPage(QWidget):
    def __init__(self, controller, tr, notify):
        super().__init__()
        self.controller = controller
        self.notify = notify
        root = QVBoxLayout(self)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setObjectName("StatValue")
        self.summary.setStyleSheet("font-size: 16px;")
        root.addWidget(self.summary)
        self.chart = SessionChart()
        root.addWidget(self.chart)
        self.history = QListWidget()
        root.addWidget(self.history)
        row = QHBoxLayout()
        csv_btn = QPushButton("Export CSV")
        csv_btn.clicked.connect(lambda: self._export("csv"))
        json_btn = QPushButton("Export JSON")
        json_btn.clicked.connect(lambda: self._export("json"))
        row.addWidget(csv_btn)
        row.addWidget(json_btn)
        root.addLayout(row)
        self.refresh()

    def refresh(self) -> None:
        data = self.controller.db.analytics_summary()
        tops = ", ".join(
            f"{item['profile_name']} ({item['uses']})" for item in data["top_profiles"]
        ) or "—"
        self.summary.setText(
            f"Clicks {data['clicks']}    Sessions {data['sessions']}\n"
            f"Average {data['average_cps']:.2f}/s    Time {format_duration(data['duration_ms'])}\n"
            f"Most used: {tops}"
        )
        self.history.clear()
        sessions = self.controller.db.sessions(50)
        self.chart.set_values([int(row["clicks"]) for row in reversed(sessions)])
        if not sessions:
            self.history.addItem("No sessions yet. Statistics appear after a real run.")
            return
        peak = max(int(row["clicks"]) for row in sessions) or 1
        for row in sessions:
            bar = "█" * max(1, int(20 * int(row["clicks"]) / peak)) if int(row["clicks"]) else "·"
            self.history.addItem(
                f"{row['ended_at']}  {row['profile_name']}  {row['clicks']} clicks  "
                f"{format_duration(row['duration_ms'])}  {bar}"
            )

    def _export(self, kind: str) -> None:
        suffix = "csv" if kind == "csv" else "json"
        path, _ = QFileDialog.getSaveFileName(self, "Export statistics", f"stats.{suffix}", f"*.{suffix}")
        if not path:
            return
        text = self.controller.export_stats(kind)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.notify(f"Exported {suffix.upper()}")


class SafetyPage(QWidget):
    def __init__(self, controller, tr, notify):
        super().__init__()
        self.controller = controller
        self.notify = notify
        policy = controller.policy
        root = QFormLayout(self)
        self.max_cps = QSpinBox()
        self.max_cps.setRange(1, policy.hard_max_cps)
        self.max_cps.setValue(policy.max_cps)
        self.session_min = QSpinBox()
        self.session_min.setRange(1, 480)
        self.session_min.setValue(max(1, policy.max_session_ms // 60000))
        self.confirm = QSpinBox()
        self.confirm.setRange(1, policy.hard_max_cps)
        self.confirm.setValue(policy.confirm_above_cps)
        self.infinite = QCheckBox("Allow infinite clicking after confirmation")
        self.infinite.setChecked(policy.allow_infinite)
        root.addRow("Maximum clicks per second", self.max_cps)
        root.addRow("Maximum session minutes", self.session_min)
        root.addRow("Ask confirmation above this CPS", self.confirm)
        root.addRow(self.infinite)
        note = QLabel(
            f"Hard limits stay in place: at least {policy.min_interval_ms} ms between cycles, "
            f"never above {policy.hard_max_cps} clicks/s, sessions never longer than 8 hours. "
            "There is no hidden mode and the app does not request administrator rights."
        )
        note.setWordWrap(True)
        note.setObjectName("Muted")
        root.addRow(note)
        save = QPushButton(tr("save"))
        save.clicked.connect(self._save)
        root.addRow(save)
        clear = QPushButton("Clear active automation")
        clear.clicked.connect(self._clear)
        root.addRow(clear)

    def _save(self) -> None:
        policy = SafetyPolicy(
            max_cps=self.max_cps.value(),
            max_session_ms=self.session_min.value() * 60_000,
            confirm_above_cps=self.confirm.value(),
            allow_infinite=self.infinite.isChecked(),
        )
        saved = self.controller.update_safety(policy)
        self.notify(f"Safety saved. Maximum {saved.max_cps} clicks/s.")

    def _clear(self) -> None:
        self.controller.clear_tasks()
        self.notify("Active automation cleared")


class SettingsPage(QWidget):
    def __init__(self, controller, tr, notify, apply_appearance):
        super().__init__()
        self.controller = controller
        self.tr = tr
        self.notify = notify
        self.apply_appearance = apply_appearance
        root = QFormLayout(self)
        self.language = QComboBox()
        self.language.addItem("English", "en")
        self.language.addItem("العربية", "ar")
        lang = controller.db.get_setting("language") or "en"
        self.language.setCurrentIndex(0 if lang == "en" else 1)
        self.theme = QComboBox()
        self.theme.addItems(["dark", "light"])
        self.theme.setCurrentText(controller.db.get_setting("theme") or "dark")
        self.accent = QComboBox()
        self.accent.addItems(ACCENTS)
        current = controller.db.get_setting("accent") or ACCENTS[0]
        if current not in ACCENTS:
            self.accent.addItem(current)
        self.accent.setCurrentText(current)
        self.minimized = QCheckBox("Start minimized to the tray")
        self.minimized.setChecked(controller.db.get_setting("start_minimized") == "1")
        self.tray = QCheckBox("Closing the window keeps the app in the tray")
        self.tray.setChecked(controller.db.get_setting("close_to_tray") != "0")
        self.notifications = QCheckBox("Show status notifications")
        self.notifications.setChecked(controller.db.get_setting("notifications") != "0")
        root.addRow(tr("language"), self.language)
        root.addRow(tr("theme"), self.theme)
        root.addRow(tr("accent"), self.accent)
        root.addRow(self.minimized)
        root.addRow(self.tray)
        root.addRow(self.notifications)
        data = QLabel(str(controller.db.path))
        data.setObjectName("Muted")
        data.setWordWrap(True)
        root.addRow("Data file", data)
        save = QPushButton(tr("apply"))
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        root.addRow(save)
