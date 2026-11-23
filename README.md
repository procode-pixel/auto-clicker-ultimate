# Auto Clicker Ultimate

Premium Windows desktop auto clicker. Version 1.0.1.

## Run after downloading the source zip

1. On GitHub open Code, then Download ZIP, and unzip the folder.
2. Double-click `RUN.bat`.
3. The first run installs the libraries into `.venv` (needs internet) and then opens the window.

Python 3.10 or newer must be installed, with Add python.exe to PATH checked. The script does not ask for administrator rights.

A packaged exe is built by GitHub Actions. After the workflow finishes, download the artifact `AutoClickerUltimate-win64` from the Actions tab. That zip does not need Python. A Release is published only when a `v*` tag is pushed.

The program clicks only when you start it. It does not hide itself, it does not ask for administrator rights, and it does not run imported files as code.

## What it does

- Left, right, and middle clicks. Single, double, or a short sequence.
- Intervals in hours, minutes, seconds, and milliseconds. Fixed or random.
- A fixed count, a duration, or infinite clicking after an explicit confirmation.
- Optional start delay and a scheduled start time.
- Current cursor, one fixed point, or an ordered list of points, with an on-screen picker.
- Macro recorder and editor: reorder, duplicate, delete, insert delays, loops, import and export.
- Pixel color checks and image recognition on a region you choose. Capture stays off until you enable it.
- A step builder for click, move, key, wait, repeat, condition, and stop.
- Global hotkeys, including an emergency stop, while the window is minimized when Windows allows the hook.
- Profiles in SQLite, built-in examples, import and export.
- Session statistics exported to CSV or JSON, plus a bar chart of recent sessions.
- System tray, dark and light themes, accent color, English and Arabic (Arabic uses right-to-left layout).

## Safety limits

These ceilings are in the program and cannot be raised from Settings:

| Limit | Value |
| --- | --- |
| Shortest cycle | 15 ms |
| Fastest allowed rate | 80 clicks/s, and lower if you set a tighter maximum |
| Longest session | 8 hours, and shorter if you set a tighter maximum |
| Infinite clicking | Off until you confirm, and it can be disabled |
| Imported files | JSON only, 2 MB, known schema version 1. Fields such as `exec` or `shell` are rejected |
| Recognition images | Up to 800x800 and 1.5 MB. Flat images are ignored |

Emergency stop defaults to `Ctrl+Shift+F12`. It latches automation until you clear it.

## Build on Windows

```bat
build_windows.bat
```

The executable is `dist\AutoClickerUltimate\AutoClickerUltimate.exe`.

## Tests

```bat
set PYTHONPATH=src
py -3.12 -m unittest discover -s tests -v
```

Settings and the database are stored in `%APPDATA%\AutoClickerUltimate`.

## Arabic

### النقر التلقائي — النسخة المتقدمة

تطبيق سطح مكتب لويندوز، وليس موقعًا. النقر يحدث فقط بعد أن تبدأه أنت.

**التنزيل:** من GitHub اختر Code ثم Download ZIP، فُك الضغط، ثم شغّل `RUN.bat`. أول تشغيل يثبّت المكتبات ويحتاج بايثون 3.10 أو أحدث على الـ PATH. لا يطلب صلاحيات مدير النظام.

**الإيقاف الطارئ:** `Ctrl+Shift+F12`.

**العربية داخل البرنامج:** من الإعدادات اختر العربية. تنعكس الواجهة من اليمين إلى اليسار.
