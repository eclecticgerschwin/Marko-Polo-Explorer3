@echo off
:: Marko Polo Explorer - Silent GUI Launcher
:: This is the shortcut target — launches the app without a console window.
cd /d "%~dp0"

:: Auto-install PySide6 if missing (first-run only)
python -c "import PySide6" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] First-time setup: Installing PySide6...
    python -m pip install PySide6>=6.5.0 >nul 2>&1
    if %errorlevel% neq 0 (
        if exist "%~dp0requirements.txt" (
            python -m pip install -r "%~dp0requirements.txt"
        )
    )
)

:: Launch with pythonw (no console window). Fallback to python if pythonw missing.
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw "%~dp0image_capture_app.py"
) else (
    start "" python "%~dp0image_capture_app.py"
)
