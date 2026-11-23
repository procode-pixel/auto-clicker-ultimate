@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm AutoClickerUltimate.spec
echo.
echo Build folder: dist\AutoClickerUltimate\AutoClickerUltimate.exe
endlocal
