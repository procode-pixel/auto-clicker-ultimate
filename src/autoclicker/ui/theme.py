"""Design tokens for the desktop shell. Accent is user-selectable; contrast is computed."""

from __future__ import annotations


def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    r, g, b = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def stylesheet(mode: str, accent: str) -> str:
    if not (len(accent) == 7 and accent.startswith("#")):
        accent = "#c9863a"
    try:
        int(accent[1:], 16)
    except ValueError:
        accent = "#c9863a"
    on_accent = "#1a1208" if _luminance(accent) > 0.62 else "#fffaf3"
    if mode == "light":
        bg, surface, elevated = "#f4f0e8", "#fffdf8", "#efe8dc"
        text, muted, line = "#1c1915", "#5e584e", "#ddd4c6"
        danger, ok = "#9d341f", "#2f6b45"
    else:
        bg, surface, elevated = "#12161a", "#1c2228", "#252c33"
        text, muted, line = "#f3efe6", "#a7b0b8", "#323a42"
        danger, ok = "#e07a68", "#8fbf86"
    return f"""
    QWidget {{
        background: {bg};
        color: {text};
        font-family: "Segoe UI", "Noto Sans", "Tahoma", sans-serif;
        font-size: 13px;
    }}
    QMainWindow {{ background: {bg}; }}
    QFrame#Sidebar {{ background: {surface}; border-right: 1px solid {line}; }}
    QFrame#Card {{
        background: {surface};
        border: 1px solid {line};
        border-radius: 14px;
    }}
    QLabel#Brand {{ font-size: 18px; font-weight: 700; letter-spacing: 0.4px; }}
    QLabel#Muted {{ color: {muted}; }}
    QLabel#StatValue {{ font-size: 28px; font-weight: 650; }}
    QPushButton {{
        background: {elevated};
        color: {text};
        border: 1px solid {line};
        border-radius: 10px;
        padding: 8px 14px;
        min-height: 18px;
    }}
    QPushButton:hover {{ border-color: {accent}; }}
    QPushButton:disabled {{ color: {muted}; }}
    QPushButton#Primary {{
        background: {accent};
        color: {on_accent};
        border: none;
        font-weight: 700;
    }}
    QPushButton#Danger {{
        background: {danger};
        color: #fffaf3;
        border: none;
        font-weight: 700;
    }}
    QPushButton#Nav {{
        text-align: left;
        padding: 10px 12px;
        border: none;
        background: transparent;
        border-radius: 8px;
    }}
    QPushButton#Nav[active="true"] {{
        background: {elevated};
        color: {accent};
        font-weight: 700;
    }}
    QLineEdit, QSpinBox, QComboBox, QDateTimeEdit, QPlainTextEdit, QListWidget {{
        background: {elevated};
        color: {text};
        border: 1px solid {line};
        border-radius: 8px;
        padding: 6px 8px;
        selection-background-color: {accent};
        selection-color: {on_accent};
    }}
    QCheckBox {{ spacing: 8px; }}
    QStatusBar {{ background: {surface}; color: {muted}; border-top: 1px solid {line}; }}
    QToolTip {{
        background: {elevated};
        color: {text};
        border: 1px solid {line};
        padding: 6px;
    }}
    QScrollArea {{ border: none; }}
    QListWidget::item {{ padding: 6px; }}
    QListWidget::item:selected {{ background: {accent}; color: {on_accent}; }}
    """


ACCENTS = ["#c9863a", "#3d8b8b", "#4c6e9a", "#8d4d4d", "#6a7a45"]
