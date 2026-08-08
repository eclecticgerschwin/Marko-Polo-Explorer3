@echo off
:: Marko Polo Explorer - Windows Silent GUI Launcher
title Marko Polo Explorer
cd /d "%~dp0"

:: Check if PySide6 is installed; if missing, auto-install silently
python -c "import PySide6" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] First time setup: Installing PySide6 dependencies...
    python -m pip install -r requirements.txt
)

:: Launch pythonw (no black console window!). Fallback to python if pythonw missing.
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw image_capture_app.py
) else (
    start "" python image_capture_app.py
)
