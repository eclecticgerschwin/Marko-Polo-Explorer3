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

# ─── Windows ZIP via GitHub Actions ──────────────────────────
echo ""
NEW_VER=$(python3 -c 'import json; print(json.load(open("version.json"))["version"])')
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    echo "🪟 Building Windows exe on GitHub Actions (v$NEW_VER)..."
    git add -A
    git commit -m "Release v$NEW_VER" >/dev/null 2>&1 || true
    git push origin main || { echo "   ❌ git push failed - open GitHub Desktop and push manually."; }

    gh workflow run build-windows.yml >/dev/null 2>&1
    echo "   ⏳ Waiting for the cloud build to start..."
    sleep 10
    RUN_ID=$(gh run list --workflow=build-windows.yml --limit 1 --json databaseId -q '.[0].databaseId')
    echo "   ⏳ Building on Windows runner (run $RUN_ID) - takes ~5-10 min..."
    if gh run watch "$RUN_ID" --exit-status >/dev/null 2>&1; then
        rm -rf _win_artifact MarkoPoloExplorer-Windows.zip
        gh run download "$RUN_ID" -n MarkoPoloExplorer-Windows -D _win_artifact
        find _win_artifact -name "MarkoPoloExplorer-Windows.zip" -exec cp {} . \;
        rm -rf _win_artifact
        echo "   ✅ MarkoPoloExplorer-Windows.zip downloaded to project root."
    else
        echo "   ❌ Windows build FAILED - check the Actions tab on github.com."
    fi
else
    echo "⚠️  Skipping Windows build - GitHub CLI not set up."
    echo "   One-time setup:   brew install gh    then:   gh auth login"
    echo "   (or push in GitHub Desktop and run the workflow manually)"
fi

# ─── Summary ─────────────────────────────────────────────────
echo ""
echo "✅ RELEASE v$NEW_VER - files in project root:"
echo "   1. version.json               -> upload to server (markopolo/)"
echo "   2. MarkoPoloExplorer.dmg      -> upload to server (macOS)"
echo "   3. MarkoPoloExplorer-Windows.zip -> upload to server / Google Drive"
echo "      (the exe for the Google Drive website link is inside this zip:"
echo "       Drive -> Manage versions -> Upload new version)"
echo "========================================================"
echo "Press any key to close..."
read -n 1
