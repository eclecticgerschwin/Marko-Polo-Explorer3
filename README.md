# 🧭 Marko Polo Explorer

**Marko Polo Explorer** is a high-performance cross-platform asset management, camera transfer, and dual-panel file explorer desktop application built with Python 3 and PySide6.

---

## 💻 Supported Operating Systems

- **macOS** (10.15 Catalina or newer — Apple Silicon & Intel)
- **Windows** (Windows 10 & Windows 11 — 64-bit)

---

## 🚀 Quick Start & Installation

### macOS
1. Open `MarkoPoloExplorer.dmg` or double-click `BUILD_AND_PACKAGE.command` to build fresh packages.
2. Drag **Marko Polo Explorer** to your `/Applications` folder.
3. Launch the app.

### Windows (standalone — no Python needed)
1. Download `MarkoPoloExplorer.exe` from the website (hosted on Google Drive), or `MarkoPoloExplorer-Windows.zip` and extract it.
2. Double-click `MarkoPoloExplorer.exe`. If SmartScreen appears: *More info → Run anyway* (first launch only).

---

## 🔄 Automatic Updates

- **Version Check**: The app compares its local version string (`DDMMYYHH`) against `version.json` at `http://marko.com.hr/markopolo/version.json`.
- **macOS**: downloads the update zip and applies it via detached `updater.py`.
- **Windows**: downloads `MarkoPoloExplorer-Windows.zip`, swaps the running exe with a batch script, and relaunches.

---

## 📦 Release Procedure (one command for both platforms)

One-time setup on the Mac: `brew install gh` then `gh auth login`.

For every release:
```bash
./BUILD_AND_PACKAGE.command
```
This bumps the version, builds the macOS dmg, pushes to GitHub, triggers the
cloud Windows build, waits, and downloads `MarkoPoloExplorer-Windows.zip` into
the project root. Then:

1. Upload `version.json`, `MarkoPoloExplorer.dmg`, `MarkoPoloExplorer-Windows.zip` to `marko.com.hr/markopolo/` (for big files use the split-parts + `UPLOAD_PARTS/join.php` trick).
2. Website exe: take `MarkoPoloExplorer.exe` from inside the zip → Google Drive → right-click file → *Manage versions → Upload new version* (keeps the same link).

If `gh` isn't set up, the script skips the Windows part — push in GitHub Desktop and run the "Build Windows Standalone EXE" workflow manually instead.

---

## 📚 Documentation

- 📘 **PROJECT_DOCUMENTATION.md** — architecture overview, module breakdown, and notes for future AI agents & developers. (Note: its Windows packaging chapter predates the PyInstaller/GitHub Actions flow described above — this README is the current source of truth for releases.)
