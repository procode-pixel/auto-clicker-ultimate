# Phases

All ten phases are in this tree. What was executed here is the logic and the unit suite (24 tests, Linux, fake mouse). The window itself is PySide6 and is packaged on the Windows runner; this environment has no Windows desktop and no `libEGL`, so the window was not opened here.

| Phase | Result |
| --- | --- |
| 1 Architecture and design system | Packages split. Dark/light QSS, accent list, English/Arabic tables, RTL flag. |
| 2 Main window and dashboard | Sidebar, status, start/pause/resume/stop, live counters, activity list, welcome dialog. |
| 3 Click engine | Threaded engine, interval parts, random range, count/duration/infinite, delay and schedule wait. |
| 4 Positions | Cursor, fixed point, ordered or random multi-point, on-screen picker. |
| 5 Macros | Recorder model, editor operations, playback speed and repeat, JSON validation. |
| 6 Recognition | Pixel tolerance, template match, capture switch, conditional steps. |
| 7 Builder | Click, move, key, wait, repeat, condition, stop. Repeats without a wait are rejected. |
| 8 Hotkeys and tray | Conflict checks, in-window shortcuts, global hook when the OS allows it, tray menu. |
| 9 Profiles, settings, analytics | SQLite profiles, presets, import/export, CSV and JSON stats, theme and language. |
| 10 Tests and packaging | `tests/`, PyInstaller spec, version resource, Inno Setup script, GitHub Actions workflow. |

## Not claimed

- A Windows `.exe` was not compiled in this workspace. The tag build on GitHub Actions produces it.
- Global hooks, the tray, and real cursor movement were not exercised on a Windows desktop here.
