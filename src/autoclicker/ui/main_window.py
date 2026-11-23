"""Main window, navigation, tray, and always-visible emergency stop."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from autoclicker import APP_NAME
from autoclicker.core.hotkeys import normalize_combo
from autoclicker.core.safety import ValidationError
from autoclicker.core.timing import format_duration
from autoclicker.i18n import Translator
from autoclicker.ui.pages_auto import BuilderPage, SmartPage
from autoclicker.ui.pages_click import ClickerPage, DashboardPage, PositionsPage
from autoclicker.ui.pages_macro import MacroPage
from autoclicker.ui.pages_manage import (
    AnalyticsPage,
    HotkeysPage,
    ProfilesPage,
    SafetyPage,
    SettingsPage,
)
from autoclicker.ui.theme import stylesheet


def _qt_sequence(combo: str) -> str:
    try:
        combo = normalize_combo(combo)
    except ValueError:
        return ""
    mapping = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Meta"}
    parts = []
    for part in combo.split("+"):
        if part in mapping:
            parts.append(mapping[part])
        elif part.startswith("f") and part[1:].isdigit():
            parts.append(part.upper())
        else:
            parts.append(part.upper() if len(part) == 1 else part)
    return "+".join(parts)


class MainWindow(QMainWindow):
    def __init__(self, controller, icon_path: str | None = None):
        super().__init__()
        self.controller = controller
        language = controller.db.get_setting("language") or "en"
        self.tr = Translator(language)
        self.setWindowTitle(APP_NAME)
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
            self._icon = QIcon(icon_path)
        else:
            self._icon = self.windowIcon()
        self._nav_buttons: list[QPushButton] = []
        self._local_shortcuts: list[QShortcut] = []
        self._build()
        self.apply_appearance()
        self._install_shortcuts()
        self._install_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(200)
        if controller.db.get_setting("onboarded") != "1":
            QTimer.singleShot(200, self._welcome)

    def _build(self) -> None:
        shell = QWidget()
        self.setCentralWidget(shell)
        row = QHBoxLayout(shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 18, 16, 18)
        brand = QLabel(self.tr("app_name"))
        brand.setObjectName("Brand")
        brand.setWordWrap(True)
        side.addWidget(brand)
        edition = QLabel("ULTIMATE EDITION")
        edition.setObjectName("Muted")
        side.addWidget(edition)
        side.addSpacing(12)
        self.stack = QStackedWidget()
        self.pages = {}
        notify = self._notify
        self.pages["dashboard"] = DashboardPage(self.controller, self.tr)
        self.pages["clicker"] = ClickerPage(self.controller, self.tr, notify)
        self.pages["positions"] = PositionsPage(self.controller, self.pages["clicker"], self.tr, notify)
        self.pages["macros"] = MacroPage(self.controller, self.tr, notify)
        self.pages["smart"] = SmartPage(self.controller, self.tr, notify)
        self.pages["builder"] = BuilderPage(self.controller, self.tr, notify)
        self.pages["hotkeys"] = HotkeysPage(
            self.controller, self.tr, notify, on_saved=self._install_shortcuts
        )
        self.pages["profiles"] = ProfilesPage(self.controller, self.pages["clicker"], self.tr, notify)
        self.pages["analytics"] = AnalyticsPage(self.controller, self.tr, notify)
        self.pages["safety"] = SafetyPage(self.controller, self.tr, notify)
        self.pages["settings"] = SettingsPage(self.controller, self.tr, notify, self.apply_appearance)
        order = [
            ("dashboard", "dashboard"),
            ("clicker", "clicker"),
            ("positions", "positions"),
            ("macros", "macros"),
            ("smart", "smart"),
            ("builder", "builder"),
            ("hotkeys", "hotkeys"),
            ("profiles", "profiles"),
            ("analytics", "analytics"),
            ("safety", "safety"),
            ("settings", "settings"),
        ]
        for key, label_key in order:
            button = QPushButton(self.tr(label_key))
            button.setObjectName("Nav")
            button.setProperty("active", "false")
            button.clicked.connect(lambda _=False, name=key: self.show_page(name))
            side.addWidget(button)
            self._nav_buttons.append(button)
            self.stack.addWidget(self.pages[key])
        side.addStretch(1)
        self.emergency = QPushButton(self.tr("emergency"))
        self.emergency.setObjectName("Danger")
        self.emergency.setToolTip("Stops every worker immediately and latches until you clear it.")
        self.emergency.clicked.connect(self._emergency)
        side.addWidget(self.emergency)
        row.addWidget(sidebar)
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(18, 16, 18, 12)
        header = QHBoxLayout()
        self.status_pill = QLabel(self.tr("idle"))
        self.status_pill.setObjectName("Brand")
        header.addWidget(self.status_pill)
        header.addStretch(1)
        for key, slot, primary in (
            ("start", self._start, True),
            ("pause", self.controller.pause, False),
            ("resume", self._resume, False),
            ("stop", self.controller.stop, False),
        ):
            button = QPushButton(self.tr(key))
            if primary:
                button.setObjectName("Primary")
            button.clicked.connect(slot)
            header.addWidget(button)
        column.addLayout(header)
        column.addWidget(self.stack, 1)
        row.addWidget(content, 1)
        status = QStatusBar()
        self.setStatusBar(status)
        self.footer = QLabel("Ready")
        status.addWidget(self.footer)
        self.show_page("dashboard")

    def show_page(self, name: str) -> None:
        keys = list(self.pages)
        index = keys.index(name)
        self.stack.setCurrentIndex(index)
        for button, key in zip(self._nav_buttons, keys):
            button.setProperty("active", "true" if key == name else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        if name == "positions":
            self.pages["positions"].sync_from_clicker()
        if name == "analytics":
            self.pages["analytics"].refresh()
        if name == "profiles":
            self.pages["profiles"].reload()

    def apply_appearance(self) -> None:
        language = self.controller.db.get_setting("language") or "en"
        self.tr.set(language)
        mode = self.controller.db.get_setting("theme") or "dark"
        accent = self.controller.db.get_setting("accent") or "#c9863a"
        self.setStyleSheet(stylesheet(mode, accent))
        direction = Qt.LayoutDirection.RightToLeft if self.tr.rtl else Qt.LayoutDirection.LeftToRight
        self.setLayoutDirection(direction)
        self.setWindowTitle(self.tr("app_name"))

    def _install_shortcuts(self) -> None:
        for shortcut in self._local_shortcuts:
            shortcut.setEnabled(False)
        self._local_shortcuts.clear()
        for action, combo in self.controller.hotkey_map().items():
            sequence = _qt_sequence(combo)
            if not sequence:
                continue
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(lambda name=action: self.controller._on_hotkey(name))
            self._local_shortcuts.append(shortcut)

    def _install_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        self.tray = QSystemTrayIcon(self._icon, self)
        menu = QMenu()
        for label, slot in (
            (self.tr("tray_open"), self._restore),
            (self.tr("start"), self._start),
            (self.tr("pause"), self.controller.pause),
            (self.tr("stop"), self.controller.stop),
            (self.tr("emergency"), self._emergency),
            (self.tr("tray_exit"), self._exit),
        ):
            action = QAction(label, self)
            action.triggered.connect(slot)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self._refresh_tray()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._restore()

    def _restore(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _refresh_tray(self) -> None:
        if not getattr(self, "tray", None):
            return
        stats = self.controller.snapshot()
        self.tray.setToolTip(f"{APP_NAME} — {stats.state} — {stats.clicks} clicks")

    def _tick(self) -> None:
        stats = self.controller.snapshot()
        self.pages["dashboard"].refresh()
        if self.stack.currentWidget() is self.pages["positions"]:
            self.pages["positions"].refresh_cursor()
        self.controller.note_macro_finished()
        self.controller.note_workflow_finished()
        latch = "  ·  EMERGENCY LATCH" if self.controller.emergency_latched else ""
        self.status_pill.setText(f"{stats.state.upper()}{latch}")
        self.footer.setText(
            f"{stats.profile_name or 'No profile'}   ·   {stats.clicks} clicks   ·   "
            f"{stats.cps:.1f}/s   ·   {format_duration(stats.elapsed_ms)}"
        )
        self._refresh_tray()

    def _start(self) -> None:
        if self.controller.emergency_latched:
            self._notify("Clear the emergency latch in Safety before starting.")
            return
        try:
            job = self.pages["clicker"].build_job()
            name = self.pages["clicker"].profile_name.text().strip() or "Manual"
            self.controller.start_job(job, name)
            self.show_page("dashboard")
        except ValidationError as exc:
            self._notify(str(exc))
        except Exception as exc:  # noqa: BLE001
            self._notify(str(exc))

    def _resume(self) -> None:
        try:
            self.controller.resume()
        except Exception as exc:  # noqa: BLE001
            self._notify(str(exc))

    def _emergency(self) -> None:
        self.controller.emergency_stop()
        self._notify("Emergency stop. Automation is latched until you clear it.")

    def _welcome(self) -> None:
        QMessageBox.information(self, self.tr("welcome_title"), self.tr("welcome_body"))
        self.controller.db.set_setting("onboarded", "1")

    def _notify(self, message: str) -> None:
        self.footer.setText(message)
        self.controller.db.log_activity(message)
        if self.controller.db.get_setting("notifications") == "0":
            return
        if getattr(self, "tray", None):
            self.tray.showMessage(APP_NAME, message, QSystemTrayIcon.MessageIcon.Information, 2500)

    def closeEvent(self, event):  # noqa: N802 - Qt override
        to_tray = self.controller.db.get_setting("close_to_tray") != "0"
        if to_tray and getattr(self, "tray", None) and self.tray.isVisible() and not self._exiting:
            event.ignore()
            self.hide()
            return
        self.timer.stop()
        if getattr(self, "tray", None):
            self.tray.hide()
        self.controller.shutdown()
        event.accept()

    def _exit(self) -> None:
        self._exiting = True
        self.close()

    _exiting = False
