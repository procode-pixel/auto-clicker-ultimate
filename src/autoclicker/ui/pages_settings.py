"""Settings page. Separate module so the save handler cannot be dropped."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QPushButton, QWidget

from autoclicker.ui.theme import ACCENTS


class SettingsPage(QWidget):
    def __init__(self, controller, tr, notify, apply_appearance):
        super().__init__()
        self.controller = controller
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
        save.clicked.connect(self.save_settings)
        root.addRow(save)

    def save_settings(self) -> None:
        db = self.controller.db
        db.set_setting("language", self.language.currentData())
        db.set_setting("theme", self.theme.currentText())
        db.set_setting("accent", self.accent.currentText())
        db.set_setting("start_minimized", "1" if self.minimized.isChecked() else "0")
        db.set_setting("close_to_tray", "1" if self.tray.isChecked() else "0")
        db.set_setting("notifications", "1" if self.notifications.isChecked() else "0")
        self.apply_appearance()
        self.notify("Settings applied")
