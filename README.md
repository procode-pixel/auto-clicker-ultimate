# Auto Clicker Ultimate

Premium Windows desktop auto clicker. Version 1.0.0.

The program clicks only when you start it. It does not hide itself, it does not ask for administrator rights, and it does not run imported files as code.

## Download

Windows builds are produced on GitHub Actions from a clean Windows runner.

1. Open the [Releases](https://github.com/procode-pixel/auto-clicker-ultimate/releases) page.
2. Download `AutoClickerUltimate-win64.zip` from the latest `v*` release.
3. Unzip it and run `AutoClickerUltimate.exe`.

Python does not need to be installed. If the release is still building, the same zip is attached to the workflow run as an artifact named `AutoClickerUltimate-win64`.

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
- Session statistics exported to CSV or JSON.
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
| Recognition images | Up to 800×800 and 1.5 MB. Flat images are ignored |

Emergency stop defaults to `Ctrl+Shift+F12`. It latches automation until you clear it.

## Build on Windows

```bat
build_windows.bat
```

Or:

```bat
py -3.12 -m pip install -r requirements.txt
py -3.12 -m PyInstaller --noconfirm AutoClickerUltimate.spec
```

The executable is `dist\AutoClickerUltimate\AutoClickerUltimate.exe`.

An optional Inno Setup script is in `installer/AutoClickerUltimate.iss`.

## Tests

From this folder:

```bat
set PYTHONPATH=src
py -3.12 -m unittest discover -s tests -v
```

The automated tests cover timing, buttons, positions, start and stop, pause, the session cap, macro editing and playback, import rejection, hotkey conflicts, profile storage, image and pixel detection, workflow loops, and the emergency latch. They use a fake mouse so they do not move your cursor. A real click still requires the Windows app.

## Layout

```text
src/autoclicker/core        engine, macros, recognition, safety
src/autoclicker/storage     SQLite and validated import/export
src/autoclicker/platform    Win32 input, pynput fallback, screen capture
src/autoclicker/ui          PySide6 window, tray, picker
tests                       unit tests
```

Run from source, after installing the requirements:

```bat
set PYTHONPATH=src
py -3.12 -m autoclicker
```

Settings and the database are stored in `%APPDATA%\AutoClickerUltimate`.

## Arabic

### النقر التلقائي — النسخة المتقدمة

تطبيق سطح مكتب لويندوز، وليس موقعًا. النقر يحدث فقط بعد أن تبدأه أنت.

**التنزيل:** من صفحة الإصدارات على GitHub، ملف `AutoClickerUltimate-win64.zip`. فُك الضغط ثم شغّل `AutoClickerUltimate.exe`. لا تحتاج إلى تثبيت بايثون، ولا يطلب البرنامج صلاحيات مدير النظام.

**الإيقاف الطارئ:** `Ctrl+Shift+F12`.

**العربية داخل البرنامج:** من الإعدادات اختر العربية. تنعكس الواجهة من اليمين إلى اليسار.

**ما الذي يفعله:** نقر أيسر وأيمن وأوسط، فاصل زمني ثابت أو عشوائي، موضع المؤشر أو نقطة ثابتة أو عدة نقاط، تسجيل ماكرو وتحريره، فحص لون ونقطة وصورة داخل منطقة تحددها، ملفات إعداد، إحصاءات، وأيقونة بجانب الساعة.

**حدود الأمان:** لا يقل الفاصل عن 15 مللي ثانية، ولا تتجاوز السرعة 80 نقرة في الثانية، والملفات المستوردة بيانات JSON فقط وليست برامجًا.

التفاصيل الإنجليزية في بقية هذا الملف، وشرح البناء في `docs/BUILD.md`.
