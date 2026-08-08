@echo off
cd /d "%~dp0"
title Marko Polo Explorer - Uninstaller

cls
echo ================================================================
echo        Marko Polo Explorer - Uninstaller
echo ================================================================
echo.
echo This will remove Marko Polo Explorer from your computer:
echo   - Application folder: %LOCALAPPDATA%\MarkoPoloExplorer
echo   - Desktop shortcut
echo   - Start Menu shortcut
echo.
echo Your Python installation and PySide6 will NOT be removed.
echo.

set /p CONFIRM="Are you sure you want to uninstall? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo.
    echo Uninstall cancelled.
    pause
    exit /b 0
)

echo.
echo [Step 1/3] Removing Desktop shortcut...
set "SHORTCUT_NAME=Marko Polo Explorer"
set "DESKTOP_LNK=%USERPROFILE%\Desktop\%SHORTCUT_NAME%.lnk"
if exist "%DESKTOP_LNK%" (
    del /f /q "%DESKTOP_LNK%" >nul 2>&1
    echo [OK] Desktop shortcut removed.
) else (
    echo [SKIP] Desktop shortcut not found.
)
echo.

echo [Step 2/3] Removing Start Menu shortcut...
set "STARTMENU_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\%SHORTCUT_NAME%.lnk"
if exist "%STARTMENU_LNK%" (
    del /f /q "%STARTMENU_LNK%" >nul 2>&1
    echo [OK] Start Menu shortcut removed.
) else (
    echo [SKIP] Start Menu shortcut not found.
)
echo.

echo [Step 3/3] Removing application files...
set "INSTALL_DIR=%LOCALAPPDATA%\MarkoPoloExplorer"
if exist "%INSTALL_DIR%" (
    :: Remove all files except this running uninstaller
    for %%F in ("%INSTALL_DIR%\*") do (
        if /i not "%%~nxF"=="Uninstall Marko Polo Explorer.bat" (
            del /f /q "%%F" >nul 2>&1
        )
    )
    :: Remove subdirectories
    for /d %%D in ("%INSTALL_DIR%\*") do (
        rmdir /s /q "%%D" >nul 2>&1
    )
    echo [OK] Application files removed.
) else (
    echo [SKIP] Install directory not found.
)
echo.

echo ================================================================
echo   [SUCCESS] Marko Polo Explorer has been uninstalled.
echo ================================================================
echo.
echo Press any key to close this window...
pause >nul

:: Self-delete: schedule removal of install directory (including this script)
if exist "%INSTALL_DIR%" (
    cmd /c "timeout /t 2 /nobreak >nul & rmdir /s /q \"%INSTALL_DIR%\"" >nul 2>&1
)
exit /b 0
