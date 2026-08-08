# 🚀 Server Upload & Auto-Update Instructions

This document explains how to package and upload updates for **Marko Polo Explorer** to your web server (`http://marko.com.hr/public_html/markopolo/`).

---

## 1. How the Auto-Update System Works

1. When a user clicks **`🔄 Update`** in **Marko Polo Explorer**, the app opens a popup dialog and contacts your server URL:
   ```
   http://marko.com.hr/public_html/markopolo/version.json
   ```
2. The app compares its local version string (`__version__ = "29072622"`) with the `"version"` field in `version.json`.
3. If the server has a newer version string:
   - The popup dialog displays: **`🚀 Update Available: v29072622!`**.
   - The user can click **`📥 Download & Install Update`** which downloads either `MAC.zip` or `WINDOWS.zip` from your server and updates the application automatically.
4. If the version is up to date:
   - The popup dialog displays: **`✅ You Have the Latest Version (v29072622)`**.

---

## 2. Automatic Date & Hour Versioning (`DDMMYYHH`)

Versions are automatically formatted using current date and hour codes in 24h format (e.g. `29072622` for **29 July 2026 at 22:00**).

To automatically update all version strings in `version.json` and all application Python files before publishing:
```bash
python3 update_version.py
```

---

## 3. Files to Upload to the Server

You need to upload the following files/directories to your web server:

| Local File / Folder | Server Upload URL | Description |
| :--- | :--- | :--- |
| **`version.json`** | `http://marko.com.hr/public_html/markopolo/version.json` | Contains version info & zip URLs |
| **`MarkoPoloExplorer.dmg`** | `http://marko.com.hr/public_html/markopolo/MarkoPoloExplorer.dmg` | macOS Installer Disk Image (Drag to /Applications) |
| **`MAC.zip`** | `http://marko.com.hr/public_html/markopolo/MAC.zip` | Zip package for macOS |
| **`MarkoPoloExplorer.zip`** | `http://marko.com.hr/public_html/markopolo/MarkoPoloExplorer.zip` | Zip package for Windows |
| **`www/`** | `http://marko.com.hr/public_html/markopolo/` | Landing page website & documentation |

---

## 4. One-Click Packaging

Double-click **`BUILD_AND_PACKAGE.command`** in Finder (or **`BUILD_AND_PACKAGE.bat`** on Windows) to automatically:
1. Bump the version date code.
2. Create fresh **`MarkoPoloExplorer.dmg`**, **`MAC.zip`**, **`WINDOWS.zip`**, and **`version.json`** in your project root directory.

---

## 5. Summary Checklist Before Uploading

- [x] Double-click `BUILD_AND_PACKAGE.command` (or run `python3 update_version.py`)
- [x] Upload `version.json` to `http://marko.com.hr/public_html/markopolo/version.json`
- [x] Upload `MarkoPoloExplorer.dmg` to `http://marko.com.hr/public_html/markopolo/MarkoPoloExplorer.dmg`
- [x] Upload `MAC.zip` to `http://marko.com.hr/public_html/markopolo/MAC.zip`
- [x] Upload `MarkoPoloExplorer.zip` to `http://marko.com.hr/public_html/markopolo/MarkoPoloExplorer.zip`
- [x] Upload `www/` contents to `http://marko.com.hr/public_html/markopolo/`
