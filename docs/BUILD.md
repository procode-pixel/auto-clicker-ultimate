# Build

The supported way to produce `AutoClickerUltimate.exe` is the GitHub Actions workflow `.github/workflows/windows-build.yml` on `windows-latest` with Python 3.12. A Linux machine cannot produce that Windows executable.

Local Windows build:

1. Install Python 3.12 from python.org. Add it to PATH. Do not install as administrator unless you want to.
2. Open a command prompt in this folder.
3. Run `build_windows.bat`.
4. Run `dist\AutoClickerUltimate\AutoClickerUltimate.exe`.

The folder next to the exe contains Qt and the other libraries. Distribute the whole folder, or the zip the workflow creates: `release/AutoClickerUltimate-win64.zip`.

Version metadata is embedded from `version_info.txt`. The window icon is `assets/icon.ico`.

Optional installer: install Inno Setup 6, build the exe first, then compile `installer/AutoClickerUltimate.iss`. The installer does not request administrator rights (`PrivilegesRequired=lowest`).

## Self-check without a window

```bat
set PYTHONPATH=src
py -3 -m autoclicker --self-check
```

Prints `SELF-CHECK OK` when the built-in profiles pass validation.
