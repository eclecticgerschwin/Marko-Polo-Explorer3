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

## 📦 Release Procedure

### Windows release (built by GitHub Actions — works from the Mac)
1. Edit and test the app, then in **GitHub Desktop**: Commit to main → **Push origin**.
2. On github.com → repo → **Actions** → "Build Windows Standalone EXE" → **Run workflow** (~5–10 min). Version is bumped automatically.
3. Download the artifact: contains `MarkoPoloExplorer-Windows.zip` + `version.json`.
4. Upload both to `marko.com.hr/markopolo/` (if FTP fails on big files, split into parts and use `UPLOAD_PARTS/join.php` on the server).
5. To refresh the website exe: take `MarkoPoloExplorer.exe` from inside the zip → Google Drive → right-click the file → *Manage versions → Upload new version* (keeps the same link).

### macOS release
```bash
./BUILD_AND_PACKAGE.command
```
Then upload `MarkoPoloExplorer.dmg` and `version.json` as usual.

---

## 📚 Documentation

- 📘 **PROJECT_DOCUMENTATION.md** — architecture overview, module breakdown, and notes for future AI agents & developers. (Note: its Windows packaging chapter predates the PyInstaller/GitHub Actions flow described above — this README is the current source of truth for releases.)
