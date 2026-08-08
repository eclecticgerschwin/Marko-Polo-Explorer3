#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "========================================================"
echo "🚀 Marko Polo Explorer - Automatic Packaging & Release"
echo "========================================================"

python3 update_version.py

echo ""
echo "🧹 Scrubbing developer logs, session history, and internal build scripts..."
rm -f MAC/*.log MAC/*_log.txt MAC/*_session.json
rm -f WINDOWS/*.log WINDOWS/*_log.txt WINDOWS/*_session.json WINDOWS/build_windows_exe.bat WINDOWS/install_requirements.bat
rm -f "MAC/Marko Polo Explorer v1.0.app/Contents/Resources/"*.log "MAC/Marko Polo Explorer v1.0.app/Contents/Resources/"*_log.txt "MAC/Marko Polo Explorer v1.0.app/Contents/Resources/"*_session.json

# ─── Sync root app source → WINDOWS/ ────────────────────────
echo ""
echo "🔄 Syncing app source code to WINDOWS/..."
SYNC_FILES=(
    "image_capture_app.py"
    "updater.py"
    "version.json"
    "requirements.txt"
    "markopolo.ico"
    "markopolo.png"
    "markopolo_animated.gif"
    "folder.png"
    "folder2.png"
    "ARW-active.png"
    "ARW-buttons not active.png"
    "ARW button clicked left.png"
    "ARW button clicked right.png"
)
for f in "${SYNC_FILES[@]}"; do
    if [ -f "$f" ]; then
        cp "$f" "WINDOWS/$f"
    fi
done
echo "   ✅ WINDOWS/ folder synced with latest source."

# ─── macOS .app Bundle ───────────────────────────────────────
echo "📱 Bundling self-contained macOS App Resources..."
cp MAC/image_capture_app.py MAC/version.json MAC/updater.py MAC/*.png MAC/*.ico MAC/*.gif MAC/*.json "MAC/Marko Polo Explorer v1.0.app/Contents/Resources/" 2>/dev/null
mkdir -p "MAC/Marko Polo Explorer v1.0.app/Contents/MacOS"
cat << 'EOF' > "MAC/Marko Polo Explorer v1.0.app/Contents/MacOS/Marko Polo Explorer"
#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../Resources" && pwd )"
cd "$DIR"

export PATH="/usr/local/bin:/opt/homebrew/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:$HOME/Library/Python/3.9/bin:$HOME/Library/Python/3.10/bin:$HOME/Library/Python/3.11/bin:$HOME/Library/Python/3.12/bin:$PATH"

PY=$(which python3 || echo python3)
exec "$PY" image_capture_app.py "$@"
EOF
chmod +x "MAC/Marko Polo Explorer v1.0.app/Contents/MacOS/Marko Polo Explorer"

echo "🧹 Cleaning permissions and Apple extended attributes..."
chmod -R 755 MAC WINDOWS 2>/dev/null
xattr -rc MAC WINDOWS 2>/dev/null
find MAC WINDOWS -name ".DS_Store" -delete 2>/dev/null
find MAC WINDOWS -name "._*" -delete 2>/dev/null
codesign --force --deep --sign - "MAC/Marko Polo Explorer v1.0.app" 2>/dev/null

# ─── macOS DMG ───────────────────────────────────────────────
echo "📦 Creating MarkoPoloExplorer.dmg installer..."
rm -f MarkoPoloExplorer.dmg MAC.zip WINDOWS.zip MarkoPoloExplorer.zip
rm -rf MAC_DMG_BUILD

mkdir -p MAC_DMG_BUILD
cp -R "MAC/Marko Polo Explorer v1.0.app" MAC_DMG_BUILD/
ln -s /Applications "MAC_DMG_BUILD/Applications"
hdiutil create -volname "Marko Polo Explorer" -srcfolder MAC_DMG_BUILD -ov -format UDZO MarkoPoloExplorer.dmg >/dev/null 2>&1
rm -rf MAC_DMG_BUILD

# ─── Windows ZIP (source fallback for users without Nuitka exe) ──
echo "📦 Creating MarkoPoloExplorer.zip for Windows..."
rm -rf WIN_ZIP_BUILD MarkoPoloExplorer.zip
mkdir -p WIN_ZIP_BUILD/program

# Copy the top-level installer and uninstaller batch files
cp "WINDOWS/Install Marko Polo Explorer.bat" "WIN_ZIP_BUILD/Install Marko Polo Explorer.bat"
cp "WINDOWS/Uninstall Marko Polo Explorer.bat" "WIN_ZIP_BUILD/Uninstall Marko Polo Explorer.bat" 2>/dev/null || true

# Copy all program files into program/ subfolder
cp -R WINDOWS/* WIN_ZIP_BUILD/program/ 2>/dev/null || true

# Remove files that should NOT be in the ZIP
rm -f "WIN_ZIP_BUILD/program/Install Marko Polo Explorer.bat"
rm -f "WIN_ZIP_BUILD/program/Uninstall Marko Polo Explorer.bat"
rm -f "WIN_ZIP_BUILD/program/ONE_CLICK_INSTALL.bat"
rm -f "WIN_ZIP_BUILD/program/gui_installer.py"
rm -f "WIN_ZIP_BUILD/program/installer.py"
rm -f WIN_ZIP_BUILD/program/Install_MarkoPoloExplorer.exe
rm -f WIN_ZIP_BUILD/program/python-installer.exe
rm -f WIN_ZIP_BUILD/program/*.log
rm -f WIN_ZIP_BUILD/program/*_log.txt
rm -f WIN_ZIP_BUILD/program/*_session.json
rm -f WIN_ZIP_BUILD/program/installer_nuitka.iss
rm -f WIN_ZIP_BUILD/program/installer.nsi
rm -f WIN_ZIP_BUILD/program/installer.iss

# Create the ZIP
cd WIN_ZIP_BUILD && zip -q -r -X ../MarkoPoloExplorer.zip . \
    -x "*.DS_Store" -x "__MACOSX/*" -x "*/._*" \
    && cd ..
rm -rf WIN_ZIP_BUILD

echo "   ✅ MarkoPoloExplorer.zip packaged."

echo ""
echo "📋 ZIP contents:"
zipinfo -1 MarkoPoloExplorer.zip 2>/dev/null | head -30

# ─── Summary ─────────────────────────────────────────────────
echo ""
echo "✅ SUCCESS! Package release files generated in project root:"
echo "   1. version.json"
echo "   2. MarkoPoloExplorer.dmg  (macOS Drag to /Applications)"
echo "   3. MarkoPoloExplorer.zip  (Windows Self-Installing Package)"
echo ""
echo "   💡 NOTE: For Standalone Nuitka .exe, push to GitHub Actions"
echo "      to build on a real Windows cloud runner!"
echo "========================================================"
echo "Press any key to close..."
read -n 1
