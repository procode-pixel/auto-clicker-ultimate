"""Profiles, hotkeys, analytics, and safety. Settings live in pages_settings."""

from __future__ import annotations

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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from autoclicker.core.hotkeys import DEFAULT_BINDINGS
from autoclicker.core.models import SafetyPolicy
from autoclicker.core.timing import format_duration
from autoclicker.ui.chart_widget import SessionChart
from autoclicker.ui.pages_settings import SettingsPage

__all__ = ["ProfilesPage", "HotkeysPage", "AnalyticsPage", "SafetyPage", "SettingsPage"]


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
            mark = " \u00b7 default" if profile.is_default else ""
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
            self.notify("Shortcuts saved.")
