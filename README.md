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

### Windows
1. Extract `MarkoPoloExplorer.zip`.
2. Double-click `Install Marko Polo Explorer.bat`.
3. The installer will check/install Python & PySide6 dependencies automatically, create Desktop & Start Menu shortcuts, and launch the application.

---

## 🔄 Automatic Updates & Server Deployment

Marko Polo Explorer features an automatic detached updater:
- **Version Check**: Compares local version string (`DDMMYYHH`) against `version.json` on the update server (`http://marko.com.hr/public_html/markopolo/version.json`).
- **Detached Auto-Update**: Downloads `MAC.zip` or `MarkoPoloExplorer.zip`, spawns `updater.py` as an independent process, closes the main app, extracts files over the install directory, and relaunches cleanly.

To bump version and build packages:
```bash
python3 update_version.py
./BUILD_AND_PACKAGE.command
```

---

## 📚 Documentation & Developer Guides

- 📘 **[Complete Technical Architecture & Developer Guide](file:///Users/marko/Desktop/Marko%20Polo%20Explorer/PROJECT_DOCUMENTATION.md)** — Comprehensive architecture overview, module breakdown, build system, and instructions for future AI agents & developers.
- 🚀 **[Server Upload Instructions](file:///Users/marko/Desktop/Marko%20Polo%20Explorer/SERVER_UPLOAD_INSTRUCTIONS.md)** — Release checklist and file upload guide for web hosting.
