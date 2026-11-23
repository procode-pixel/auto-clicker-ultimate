# -*- mode: python ; coding: utf-8 -*-
"""Windows bundle. Build on Windows with: pyinstaller AutoClickerUltimate.spec"""

from PyInstaller.utils.hooks import collect_all

datas = [("assets", "assets")]
binaries = []
hiddenimports = [
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    "pynput.keyboard._xorg",
    "pynput.mouse._xorg",
]
pyside_datas, pyside_binaries, pyside_hidden = collect_all("PySide6")
datas += pyside_datas
binaries += pyside_binaries
hiddenimports += pyside_hidden

a = Analysis(
    ["src/autoclicker/__main__.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoClickerUltimate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/icon.ico",
    version="version_info.txt",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AutoClickerUltimate",
)
