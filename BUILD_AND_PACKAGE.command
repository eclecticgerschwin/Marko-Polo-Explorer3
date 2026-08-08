#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "========================================================"
echo "🚀 Marko Polo Explorer - macOS Packaging & Release"
echo "   (Windows exe is built by GitHub Actions, not here)"
echo "========================================================"

python3 update_version.py

echo ""
echo "🧹 Scrubbing developer logs and session history..."
rm -f MAC/*.log MAC/*_log.txt MAC/*_session.json
rm -f "MAC/Marko Polo Explorer v1.0.app/Contents/Resources/"*.log "MAC/Marko Polo Explorer v1.0.app/Contents/Resources/"*_log.txt "MAC/Marko Polo Explorer v1.0.app/Contents/Resources/"*_session.json

# ─── Sync root app source → MAC/ ─────────────────────────────
echo ""
echo "🔄 Syncing app source code to MAC/..."
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
        cp "$f" "MAC/$f"
    fi
done
echo "   ✅ MAC/ folder synced with latest source."

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
chmod -R 755 MAC 2>/dev/null
xattr -rc MAC 2>/dev/null
find MAC -name ".DS_Store" -delete 2>/dev/null
find MAC -name "._*" -delete 2>/dev/null
codesign --force --deep --sign - "MAC/Marko Polo Explorer v1.0.app" 2>/dev/null

# ─── macOS DMG ───────────────────────────────────────────────
echo "📦 Creating MarkoPoloExplorer.dmg installer..."
rm -f MarkoPoloExplorer.dmg MAC.zip
rm -rf MAC_DMG_BUILD

mkdir -p MAC_DMG_BUILD
cp -R "MAC/Marko Polo Explorer v1.0.app" MAC_DMG_BUILD/
ln -s /Applications "MAC_DMG_BUILD/Applications"
hdiutil create -volname "Marko Polo Explorer" -srcfolder MAC_DMG_BUILD -ov -format UDZO MarkoPoloExplorer.dmg >/dev/null 2>&1
rm -rf MAC_DMG_BUILD

# ─── Summary ─────────────────────────────────────────────────
echo ""
echo "✅ SUCCESS! macOS release files generated in project root:"
echo "   1. version.json"
echo "   2. MarkoPoloExplorer.dmg  (macOS - Drag to /Applications)"
echo ""
echo "   🪟 Windows release: push to GitHub (GitHub Desktop) and run"
echo "      the 'Build Windows Standalone EXE' workflow, then upload"
echo "      MarkoPoloExplorer-Windows.zip + version.json to the server."
echo "========================================================"
echo "Press any key to close..."
read -n 1
