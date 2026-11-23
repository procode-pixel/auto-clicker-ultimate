"""English and Arabic copy. Arabic switches the window to right-to-left."""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "app_name": "Auto Clicker Ultimate",
        "dashboard": "Dashboard",
        "clicker": "Click engine",
        "positions": "Positions",
        "macros": "Macros",
        "smart": "Smart automation",
        "builder": "Builder",
        "hotkeys": "Hotkeys",
        "profiles": "Profiles",
        "analytics": "Analytics",
        "safety": "Safety",
        "settings": "Settings",
        "start": "Start",
        "pause": "Pause",
        "resume": "Resume",
        "stop": "Stop",
        "emergency": "Emergency stop",
        "clear_emergency": "Clear emergency latch",
        "idle": "Idle",
        "running": "Running",
        "paused": "Paused",
        "armed": "Waiting to start",
        "clicks": "Clicks",
        "duration": "Session",
        "speed": "Speed",
        "profile": "Profile",
        "activity": "Recent activity",
        "empty_activity": "No automation has run in this installation yet.",
        "welcome_title": "Welcome",
        "welcome_body": "Auto Clicker Ultimate only runs when you start it. F6 starts the default profile, F9 stops, and Ctrl+Shift+F12 is the emergency stop. Screen capture never runs unless you enable it.",
        "language": "Language",
        "theme": "Theme",
        "accent": "Accent",
        "dark": "Dark",
        "light": "Light",
        "apply": "Apply",
        "save": "Save",
        "delete": "Delete",
        "duplicate": "Duplicate",
        "export": "Export",
        "import": "Import",
        "confirm": "I understand and want to start",
        "capture_on": "Screen capture is on",
        "capture_off": "Screen capture is off",
        "tray_open": "Open",
        "tray_exit": "Exit",
    },
    "ar": {
        "app_name": "النقر التلقائي — النسخة المتقدمة",
        "dashboard": "اللوحة",
        "clicker": "محرك النقر",
        "positions": "المواضع",
        "macros": "وحدات الماكرو",
        "smart": "الأتمتة الذكية",
        "builder": "منشئ الخطوات",
        "hotkeys": "الاختصارات",
        "profiles": "الملفات",
        "analytics": "الإحصاءات",
        "safety": "الأمان",
        "settings": "الإعدادات",
        "start": "بدء",
        "pause": "إيقاف مؤقت",
        "resume": "استئناف",
        "stop": "إيقاف",
        "emergency": "إيقاف طارئ",
        "clear_emergency": "إلغاء قفل الإيقاف الطارئ",
        "idle": "خامل",
        "running": "يعمل",
        "paused": "متوقف مؤقتًا",
        "armed": "بانتظار البدء",
        "clicks": "النقرات",
        "duration": "مدة الجلسة",
        "speed": "السرعة",
        "profile": "الملف",
        "activity": "النشاط الأخير",
        "empty_activity": "لم تعمل أي أتمتة على هذا الجهاز بعد.",
        "welcome_title": "مرحبًا",
        "welcome_body": "لا يعمل البرنامج إلا عندما تبدأه أنت. F6 يبدأ الملف الافتراضي، وF9 يوقف، وCtrl+Shift+F12 إيقاف طارئ. لا يُلتقط محتوى الشاشة إلا بعد تفعيل ذلك صراحة.",
        "language": "اللغة",
        "theme": "المظهر",
        "accent": "لون التمييز",
        "dark": "داكن",
        "light": "فاتح",
        "apply": "تطبيق",
        "save": "حفظ",
        "delete": "حذف",
        "duplicate": "نسخ",
        "export": "تصدير",
        "import": "استيراد",
        "confirm": "أفهم ذلك وأريد البدء",
        "capture_on": "التقاط الشاشة مُفعّل",
        "capture_off": "التقاط الشاشة متوقف",
        "tray_open": "فتح",
        "tray_exit": "خروج",
    },
}


class Translator:
    def __init__(self, language: str = "en"):
        self.language = language if language in STRINGS else "en"

    def set(self, language: str) -> None:
        self.language = language if language in STRINGS else "en"

    def __call__(self, key: str) -> str:
        table = STRINGS.get(self.language) or STRINGS["en"]
        return table.get(key) or STRINGS["en"].get(key, key)

    @property
    def rtl(self) -> bool:
        return self.language == "ar"
