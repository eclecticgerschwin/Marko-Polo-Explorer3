@echo off
setlocal enabledelayedexpansion
title Marko Polo Explorer - Windows Standalone Builder (PyInstaller)
cd /d "%~dp0"

echo ============================================================
echo  Marko Polo Explorer - Building standalone Windows .exe
echo  (identical to the Mac app - same Python code, same UI)
echo ============================================================
echo.

rem -- 1. Make sure Python is available -----------------------------
where python >nul 2>&1
if errorlevel 1 (
    if exist "python-3.13.15-amd64.exe" (
        echo Python not found - installing bundled Python 3.13 ...
        "python-3.13.15-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python313;%LOCALAPPDATA%\Programs\Python\Python313\Scripts;%PATH%"
    ) else (
        echo ERROR: Python not found. Install it from https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
)

rem -- 2. Bump the DDMMYYHH version everywhere ----------------------
python update_version.py

rem -- 3. Install build dependencies --------------------------------
echo Installing PySide6 + PyInstaller (first run takes a few minutes)...
python -m pip install --upgrade pip >nul
python -m pip install --upgrade PySide6 pyinstaller
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

rem -- 4. Collect asset files that exist ----------------------------
set ADDDATA=
for %%F in ("markopolo.png" "markopolo.ico" "markopolo_animated.gif" "robot_blink.gif" "ARW button clicked left.png" "ARW button clicked right.png" "ARW-active.png" "ARW-active.jpeg" "ARW-buttons not active.png" "folder.png" "folder2.png" "version.json") do (
    if exist "%%~F" set ADDDATA=!ADDDATA! --add-data "%%~F;."
)

rem -- 5. Build the one-file exe ------------------------------------
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name MarkoPoloExplorer ^
    --icon markopolo.ico ^
    !ADDDATA! ^
    image_capture_app.py
if errorlevel 1 (
    echo ERROR: PyInstaller build failed - read the log above.
    pause
    exit /b 1
)

copy /y "dist\MarkoPoloExplorer.exe" "MarkoPoloExplorer.exe" >nul

rem -- 6. Zip for the auto-updater ----------------------------------
powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\MarkoPoloExplorer.exe','version.json' -DestinationPath 'MarkoPoloExplorer.zip'"

echo.
echo ============================================================
echo  DONE! Upload these 3 files to marko.com.hr/markopolo/ :
echo    MarkoPoloExplorer.exe   (website download + windows_exe url)
echo    MarkoPoloExplorer.zip   (auto-updater download)
echo    version.json            (new version number)
echo ============================================================
pause
