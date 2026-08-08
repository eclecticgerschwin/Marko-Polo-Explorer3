# Windows Standalone Build - PyInstaller (replaces the C app)

The Windows app is now the **exact same Python program** as the Mac app, packaged with PyInstaller into a single `MarkoPoloExplorer.exe`. Same UI, same features (robot assistant, WASD map, Quick Look with video player, Magic Folders, everything). Users double-click the exe - no Python, no installer.

Your app code already supports this: `sys.frozen` detection, `get_asset_path()` lookups, and `_apply_nuitka_update()` (which also works for PyInstaller) that downloads `MarkoPoloExplorer.zip`, swaps the running exe with a batch script, and relaunches.

## How to build (two options)

**Option A - on any Windows PC (simplest):** copy this project folder to the PC and double-click `BUILD_WINDOWS_STANDALONE.bat`. It installs Python if missing (uses the bundled `python-3.13.15-amd64.exe`), bumps the version, builds the exe, and creates the updater zip. First build takes a few minutes; afterwards it's quick.

**Option B - GitHub Actions (build from your Mac, no Windows PC):** publish this folder as a GitHub repository using GitHub Desktop (you already downloaded it). The workflow in `.github/workflows/build-windows.yml` builds on Microsoft's Windows servers. Go to the repo's **Actions** tab, run "Build Windows Standalone EXE", then download the artifact zip containing the exe. Free for public repos, generous free minutes for private ones.

## Upload to the server after each build

| File | Purpose |
| :--- | :--- |
| `MarkoPoloExplorer.exe` | Website standalone download (`windows_exe` url) |
| `MarkoPoloExplorer.zip` | What the app's auto-updater downloads (`windows` url) |
| `version.json` | New version number - triggers the update popup |

Note: people who installed the earlier C-version exe will also auto-update into this Python exe - their Update button downloads whatever exe the server serves.

## Things to know

- The exe is large (~80-120 MB) because it bundles Python + Qt - normal for PySide6 apps.
- First launch takes a few seconds (one-file exes unpack to temp) - also normal.
- Windows SmartScreen will warn on first download since the exe is unsigned. Users click "More info -> Run anyway". A code-signing certificate (~$100-400/yr) removes this if it becomes a problem.
- Test the Windows build on a real Windows machine after each significant change - the Mac-only code paths (PyObjC / ImageCaptureCore) are already guarded, but new code you add must keep using those guards.
- The old C-app files in `WINDOWS_EXE/` are no longer needed - keep or delete as you like.
