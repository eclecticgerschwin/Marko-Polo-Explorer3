@echo off
cd /d "%~dp0"
echo ========================================================
echo Marko Polo Explorer - Automatic Packaging ^& Release
echo ========================================================
python update_version.py

echo.
echo Creating MAC.zip and MarkoPoloExplorer.zip...
if exist MAC.zip del /f /q MAC.zip
if exist WINDOWS.zip del /f /q WINDOWS.zip
if exist MarkoPoloExplorer.zip del /f /q MarkoPoloExplorer.zip

powershell -Command "Compress-Archive -Path 'MAC\*' -DestinationPath 'MAC.zip' -Force"
powershell -Command "Compress-Archive -Path 'WINDOWS\*' -DestinationPath 'MarkoPoloExplorer.zip' -Force"

echo.
echo SUCCESS! Package archives generated:
echo    1. version.json
echo    2. MAC.zip
echo    3. MarkoPoloExplorer.zip
echo ========================================================
pause
