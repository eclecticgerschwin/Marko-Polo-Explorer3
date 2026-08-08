@echo off
cd /d "%~dp0"
title Marko Polo Explorer - Setup Wizard

cls
echo ================================================================
echo        Marko Polo Explorer - Setup Wizard
echo        Windows 10 / 11 Installer
echo ================================================================
echo.

:: ----------------------------------------------------------------------
:: 0. CHECK IF RUNNING INSIDE UNEXTRACTED ZIP
:: ----------------------------------------------------------------------
echo "%~dp0" | findstr /i "AppData\Local\Temp" >nul
if %errorlevel% equ 0 goto ERR_ZIP

:: ----------------------------------------------------------------------
:: LOCATE SOURCE FILES
:: ----------------------------------------------------------------------
set "PROG_SOURCE=%~dp0program"
if not exist "%PROG_SOURCE%\image_capture_app.py" set "PROG_SOURCE=%~dp0"
if not exist "%PROG_SOURCE%\image_capture_app.py" goto ERR_NOFILES

:: ----------------------------------------------------------------------
:: STEP 1: DETECT OR AUTO-INSTALL PYTHON
:: ----------------------------------------------------------------------
echo [Step 1/5] Checking Python installation...
echo.

set "PY_CMD="
python -c "import sys" >nul 2>&1
if %errorlevel% equ 0 set "PY_CMD=python"
if "%PY_CMD%"=="" (
    py -3 -c "import sys" >nul 2>&1
    if %errorlevel% equ 0 set "PY_CMD=py -3"
)
if "%PY_CMD%"=="" (
    python3 -c "import sys" >nul 2>&1
    if %errorlevel% equ 0 set "PY_CMD=python3"
)

if "%PY_CMD%"=="" (
    echo [*] Python not detected on your system.
    if exist "%PROG_SOURCE%\python-installer.exe" (
        echo [*] Installing bundled Python 3.13 64-bit runtime...
        "%PROG_SOURCE%\python-installer.exe" /passive InstallAllUsers=1 PrependPath=1 Include_test=0
    ) else if exist "%~dp0python-installer.exe" (
        echo [*] Installing bundled Python 3.13 64-bit runtime...
        "%~dp0python-installer.exe" /passive InstallAllUsers=1 PrependPath=1 Include_test=0
    ) else (
        echo [*] Attempting automated Python 3.13 silent installation...
        powershell -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.13.1/python-3.13.1-amd64.exe', '$env:TEMP\python_installer.exe') } catch { exit 1 }" >nul 2>&1
        if exist "%TEMP%\python_installer.exe" (
            "%TEMP%\python_installer.exe" /quiet PrependPath=1 Include_test=0
            del /f /q "%TEMP%\python_installer.exe" >nul 2>&1
        )
    )    
        :: Refresh session PATH to pick up new Python installation
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%ProgramFiles%\Python311;%ProgramFiles%\Python311\Scripts;%PATH%"
        
        python -c "import sys" >nul 2>&1
        if %errorlevel% equ 0 set "PY_CMD=python"
        if "%PY_CMD%"=="" (
            py -3 -c "import sys" >nul 2>&1
            if %errorlevel% equ 0 set "PY_CMD=py -3"
        )
    )
)

if "%PY_CMD%"=="" goto ERR_NOPYTHON

%PY_CMD% --version
echo [OK] Python interpreter detected.

:: Verify Python version is >= 3.9 (required by PySide6)
%PY_CMD% -c "import sys; exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if %errorlevel% neq 0 goto ERR_OLDPYTHON

echo.

:: ----------------------------------------------------------------------
:: STEP 2: INSTALL PYTHON REQUIREMENTS (PySide6 & Dependencies)
:: ----------------------------------------------------------------------
echo [Step 2/5] Installing Python requirements...
echo.

if exist "%PROG_SOURCE%\requirements.txt" (
    echo [*] Installing dependencies from requirements.txt...
    %PY_CMD% -m pip install -r "%PROG_SOURCE%\requirements.txt"
) else (
    echo [*] Installing PySide6 GUI framework...
    %PY_CMD% -m pip install PySide6>=6.5.0
)

%PY_CMD% -c "import PySide6" >nul 2>&1
if %errorlevel% neq 0 goto ERR_NOPYSIDE

echo [OK] Python requirements successfully installed.
echo.

:: ----------------------------------------------------------------------
:: STEP 3: COPY APPLICATION FILES TO LOCAL APPDATA
:: ----------------------------------------------------------------------
echo [Step 3/5] Installing application files...
echo.

set "INSTALL_DIR=%LOCALAPPDATA%\MarkoPoloExplorer"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo [*] Destination: %INSTALL_DIR%

xcopy "%PROG_SOURCE%\*" "%INSTALL_DIR%\" /Y /Q >nul 2>&1
echo [OK] Application files installed.
echo.

:: ----------------------------------------------------------------------
:: STEP 4: CREATE DESKTOP AND START MENU SHORTCUTS
:: ----------------------------------------------------------------------
echo [Step 4/5] Creating Desktop and Start Menu shortcuts...
echo.

set "SHORTCUT_NAME=Marko Polo Explorer"
set "TARGET_BAT=%INSTALL_DIR%\run_app.bat"
set "ICON_FILE=%INSTALL_DIR%\markopolo.ico"
set "DESKTOP_LNK=%USERPROFILE%\Desktop\%SHORTCUT_NAME%.lnk"
set "STARTMENU_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\%SHORTCUT_NAME%.lnk"

set "VBS_HELPER=%TEMP%\mpe_shortcut.vbs"

echo Set ws = CreateObject("WScript.Shell") > "%VBS_HELPER%"
echo Set s1 = ws.CreateShortcut("%DESKTOP_LNK%") >> "%VBS_HELPER%"
echo s1.TargetPath = "%TARGET_BAT%" >> "%VBS_HELPER%"
echo s1.WorkingDirectory = "%INSTALL_DIR%" >> "%VBS_HELPER%"
echo s1.Description = "Marko Polo Explorer" >> "%VBS_HELPER%"
echo s1.IconLocation = "%ICON_FILE%" >> "%VBS_HELPER%"
echo s1.WindowStyle = 7 >> "%VBS_HELPER%"
echo s1.Save >> "%VBS_HELPER%"
echo Set s2 = ws.CreateShortcut("%STARTMENU_LNK%") >> "%VBS_HELPER%"
echo s2.TargetPath = "%TARGET_BAT%" >> "%VBS_HELPER%"
echo s2.WorkingDirectory = "%INSTALL_DIR%" >> "%VBS_HELPER%"
echo s2.Description = "Marko Polo Explorer" >> "%VBS_HELPER%"
echo s2.IconLocation = "%ICON_FILE%" >> "%VBS_HELPER%"
echo s2.WindowStyle = 7 >> "%VBS_HELPER%"
echo s2.Save >> "%VBS_HELPER%"

cscript //nologo "%VBS_HELPER%" >nul 2>&1
if exist "%VBS_HELPER%" del /f /q "%VBS_HELPER%" >nul 2>&1

echo [OK] Shortcuts created.
echo.

:: ----------------------------------------------------------------------
:: STEP 5: COPY UNINSTALLER TO INSTALL DIRECTORY
:: ----------------------------------------------------------------------
echo [Step 5/5] Installing uninstaller...
echo.

if exist "%~dp0Uninstall Marko Polo Explorer.bat" (
    copy /Y "%~dp0Uninstall Marko Polo Explorer.bat" "%INSTALL_DIR%\" >nul 2>&1
    echo [OK] Uninstaller copied to install directory.
) else (
    echo [SKIP] Uninstaller not found in package.
)
echo.

:: ----------------------------------------------------------------------
:: FINISH & AUTO-LAUNCH APPLICATION
:: ----------------------------------------------------------------------
echo ================================================================
echo   [SUCCESS] Marko Polo Explorer installed successfully!
echo   Installed to: %INSTALL_DIR%
echo   Desktop shortcut: Marko Polo Explorer
echo   To uninstall: run "Uninstall Marko Polo Explorer.bat" in the install folder.
echo.
echo   Launching Marko Polo Explorer...
echo ================================================================
echo.

cd /d "%INSTALL_DIR%"
start "" "%TARGET_BAT%"

echo Setup complete. Press any key to close this window...
pause >nul
exit /b 0

:: ----------------------------------------------------------------------
:: ERROR HANDLERS
:: ----------------------------------------------------------------------
:ERR_ZIP
echo.
echo ================================================================
echo   [!] WARNING: Running inside an unextracted ZIP file!
echo   Please EXTRACT MarkoPoloExplorer.zip first before installing:
echo    1. Right-click MarkoPoloExplorer.zip
echo    2. Select "Extract All..."
echo    3. Open the extracted folder and run "Install Marko Polo Explorer.bat"
echo ================================================================
echo.
pause
exit /b 1

:ERR_NOFILES
echo.
echo [ERROR] Cannot find application files (image_capture_app.py).
echo Please extract all files from MarkoPoloExplorer.zip and try again.
echo.
pause
exit /b 1

:ERR_NOPYTHON
echo.
echo ================================================================
echo   [ERROR] Python 3 is not installed or not in system PATH.
echo   Marko Polo Explorer requires Python 3.9 or newer.
echo.
echo   IMPORTANT during Python setup:
echo   [x] Check "Add python.exe to PATH" at the bottom of installer!
echo ================================================================
echo.
echo Opening Python download page...
start "" "https://www.python.org/downloads/"
echo.
pause
exit /b 1

:ERR_OLDPYTHON
echo.
echo ================================================================
echo   [ERROR] Python version is too old.
echo   Marko Polo Explorer requires Python 3.9 or newer.
echo   Please update Python from: https://www.python.org/downloads/
echo ================================================================
echo.
echo Opening Python download page...
start "" "https://www.python.org/downloads/"
echo.
pause
exit /b 1

:ERR_NOPYSIDE
echo.
echo [ERROR] Could not install PySide6 GUI framework.
echo Please open Command Prompt and type: pip install PySide6
echo.
pause
exit /b 1

