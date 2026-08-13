# 🧭 Marko Polo Explorer - Complete Architecture & Developer Guide

This document provides a comprehensive technical overview of **Marko Polo Explorer** for future AI agents and human developers. It details how the application works, its target operating systems, build/packaging workflows, versioning system, and auto-update mechanism.

---

## 1. Application Overview

**Marko Polo Explorer** is a high-performance cross-platform asset management and camera capture desktop application built using Python 3 and PySide6 (Qt 6). 

It acts as a hybrid between:
- **macOS Image Capture**: Live camera detection (DSLRs, Sony/Canon cameras, iPhones, SD cards).
- **Dual-Panel File Explorer**: Split file browser with thumbnail grids, quick actions, search, and batch transfer.
- **Media Player & Quick Look**: Integrated video playback via QtMultimedia, high-res photo viewer, audio player, and inspection dialogs.
- **Interactive WASD Map & Visual Widgets**: Custom UI components and spatial navigation controls.

### Target Operating Systems
1. **macOS** (`darwin`):
   - **Supported Versions**: macOS 10.15 (Catalina) and newer (Apple Silicon M1/M2/M3 & Intel x86_64).
   - **Native Features**: Interfaced directly with macOS system `ImageCaptureCore` framework via PyObjC (`ICDeviceBrowser`, `ICCameraDevice`, `ICCameraFile`).
   - **Packaging**: Bundled as a standalone macOS `.app` bundle (`Marko Polo Explorer v1.0.app`) and packaged into a `.dmg` installer (`MarkoPoloExplorer.dmg`) and `MAC.zip`.

2. **Windows** (`win32`):
   - **Supported Versions**: Windows 10 & Windows 11 (64-bit).
   - **Features**: Standalone Python runtime installer, PySide6 UI, full dual-panel filesystem explorer, simulated/Android camera asset browser, detached auto-updater.
   - **Packaging**: One-click setup batch installer (`Install Marko Polo Explorer.bat`), Uninstaller (`Uninstall Marko Polo Explorer.bat`), NSIS / Inno Setup executable (`Install_MarkoPoloExplorer.exe`), and compressed zip package (`MarkoPoloExplorer.zip`).

---

## 2. Directory Structure & Architecture

```
Marko Polo Explorer/
├── image_capture_app.py        # Main Python application source (~8,800+ lines)
├── update_version.py           # Date-coded version generator & target synchronizer
├── updater.py                  # Standalone detached auto-updater script
├── generate_windows_exe.py     # Multi-backend Windows setup EXE generator
├── version.json                # Local version metadata & remote update configuration
├── requirements.txt            # Python dependencies (PySide6, PyObjC for macOS)
├── BUILD_AND_PACKAGE.command   # One-click macOS build, sign, DMG & ZIP packager
├── BUILD_AND_PACKAGE.bat       # One-click Windows release archive packager
├── SERVER_UPLOAD_INSTRUCTIONS.md # Web server deployment checklist & instructions
├── PROJECT_DOCUMENTATION.md    # This technical guide for developers & AI agents
├── README.md                   # Quick start & documentation index
├── markopolo.ico / png / gif   # Application branding icons and visual assets
│
├── MAC/                        # macOS target distribution directory
│   ├── Marko Polo Explorer v1.0.app # macOS App Bundle skeleton
│   ├── image_capture_app.py    # Synced application code
│   ├── updater.py              # Synced updater
│   ├── version.json            # Synced version info
│   └── requirements.txt        # macOS-specific requirements (PyObjC)
│
├── WINDOWS/                    # Windows target distribution directory
│   ├── Install Marko Polo Explorer.bat   # Windows 1-click automated setup wizard
│   ├── Uninstall Marko Polo Explorer.bat # Windows uninstaller script
│   ├── image_capture_app.py    # Synced application code
│   ├── updater.py              # Synced updater
│   ├── version.json            # Synced version info
│   ├── requirements.txt        # Windows requirements
│   ├── installer.nsi / .iss    # NSIS & Inno Setup compiler scripts
│   └── python-installer.exe    # Bundled Python 3.13 64-bit installer runtime
│
└── www/                        # Web landing page & server endpoints
    ├── index.html              # Marketing website
    ├── styles.css / script.js  # Frontend assets
    └── send_mail.php           # PHP contact form endpoint
```

---

## 3. Core Software Modules & Classes

`image_capture_app.py` is structured into several modular layers:

### A. Logging & Diagnostic Subsystem
- `Tee`: Custom dual-stream wrapper directing `stdout` and `stderr` to terminal and file logs (`app_stdout.log`, `app_stderr.log`).
- `exception_logger`: Global `sys.excepthook` interceptor writing full tracebacks and timestamps to `app_crash_log.txt`.

### B. Hardware & Camera Interfacing (`PyObjC` & Fallbacks)
- `ImageCaptureManager`: Central Qt controller (`QObject`) interfacing with macOS `ImageCaptureCore`.
- `DeviceBrowserDelegate`: Intercepts `ICDeviceBrowser` events when cameras, iPhones, or SD cards are attached/detached.
- `CameraDeviceDelegate`: Handles session opening/closing, content catalog scanning, and file download signaling.
- `CameraDownloadDelegate`: Receives native file transfer callbacks.
- `SimulatedCameraFile` & `AndroidCameraFile`: Fallback representations for Windows or demo camera simulation.

### C. Async Workers & Concurrency
- `LocalThumbLoader` / `LocalThumbSignals`: Asynchronous thumbnail generator using `QThreadPool` for non-blocking UI scrolling.
- `FolderSizeWorker`: Background directory size computation thread.
- `AsyncLocationThread`: Asynchronous location & geotag resolver.
- `CheckUpdateThread` & `DownloadUpdateThread`: Background network threads for auto-update checks and binary downloads.

### D. Custom UI Components & Widgets
- `ImageCaptureClone` (`QMainWindow`): Primary window containing navigation header, dual file panels, toolbar, device list sidebar, status bar, and camera controls.
- `FilePanel` (`QWidget`): High-performance dual file explorer panel supporting list/grid views, drag-and-drop, selection rectangle overlay (`RubberBandGridWidget`), breadcrumb navigation (`NavPillWidget`), sorting, and file filtering.
- `NativeVideoPlayerWidget`: Full-featured video player with play/pause, seek slider, and audio control powered by QtMultimedia.
- `DarkQuickLookDialog` / `GetInfoDialog`: macOS QuickLook-inspired preview dialogs for full-res images, video playback, EXIF metadata inspection, and batch rename options.
- `MonthSelectDialog`: Interactive dialog in the Commands panel allowing instant filtering and selection of files by specific month (1-12), Current Month, or All across years.

---

## 4. Versioning & Build System

### Date-Coded Versioning (`DDMMYYHH`)
Versions use an automatic 8-digit date-hour format string: `DDMMYYHH` (e.g. `08082610` for **8 August 2026 at 10:00**).

To update the version across all code files:
```bash
python3 update_version.py
```
This utility:
1. Generates `date_version` based on current system time.
2. Updates `version.json` with the new string and release notes.
3. Uses regex to update `__version__ = "..."` inside `image_capture_app.py`, `MAC/image_capture_app.py`, and `WINDOWS/image_capture_app.py`.
4. Copies updated `version.json` and `updater.py` to `MAC/` and `WINDOWS/` distribution folders.

### Building Packages

#### macOS Release Build (`BUILD_AND_PACKAGE.command`)
Double-click `BUILD_AND_PACKAGE.command` or run `./BUILD_AND_PACKAGE.command` in terminal:
1. Runs `update_version.py` to bump date code.
2. Cleans developer logs and temporary session files.
3. Syncs root source files to `WINDOWS/` and `MAC/`.
4. Copies updated resources into `MAC/Marko Polo Explorer v1.0.app/Contents/Resources/`.
5. Creates executable wrapper script in `MAC/Marko Polo Explorer v1.0.app/Contents/MacOS/`.
6. Strips extended attributes (`xattr -rc`), sets POSIX permissions (`755`), and signs code locally (`codesign`).
7. Uses macOS `hdiutil` to build compressed `MarkoPoloExplorer.dmg`.
8. Packages `MarkoPoloExplorer.zip` for Windows distribution.

#### Windows Release Build (`BUILD_AND_PACKAGE.bat` / `generate_windows_exe.py`)
- On Windows: Double-click `BUILD_AND_PACKAGE.bat` to create `MarkoPoloExplorer.zip`.
- Single Executable Installer: Run `python generate_windows_exe.py`. It attempts:
  1. Inno Setup (`iscc`) if installed.
  2. NSIS (`makensis`) if installed.
  3. Universal 64-bit Windows 7zSFX setup binary direct compilation fallback on macOS.

---

## 5. Auto-Update Subsystem

```
[ App Launch / Manual Check ] 
            │
            ▼
┌─────────────────────────┐
│   CheckUpdateThread     │ ──► HTTP GET http://marko.com.hr/public_html/markopolo/version.json
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│ Version Comparison      │ ──► Local __version__ < Server version?
└─────────────────────────┘
            │ YES
            ▼
┌─────────────────────────┐
│   UpdateCheckDialog     │ ──► User clicks "Download & Install Update"
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│  DownloadUpdateThread   │ ──► Downloads MAC.zip or MarkoPoloExplorer.zip to temp folder
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│  Launch Detached Process│ ──► Spawns updater.py --zip ... --target ... --pid <current_pid>
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│   Main App Terminates   │ ──► Process closes cleanly
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│       updater.py        │ ──► Waits for PID to die ➔ Extracts ZIP over target ➔ Relaunches App
└─────────────────────────┘
```

### Detached Execution (`updater.py`)
`updater.py` runs independently from the main application process.
- **Parameters**: `--zip <path>`, `--target <path>`, `--pid <pid>`, `--launch <command>`
- **Process Wait**: Uses `ctypes.windll.kernel32.OpenProcess` on Windows or `os.kill(pid, 0)` on macOS to poll until the parent application completely exits.
- **Smart ZIP Extraction**: Handles both flat ZIP archives and installer ZIPs with a `program/` subfolder.
- **Relaunch**: Executes the launch command using `subprocess.Popen` in the target working directory.

---

## 6. Windows Installation & Uninstallation Details

### Installation (`Install Marko Polo Explorer.bat`)
1. **Unextracted ZIP Check**: Detects if user launched setup from within a Windows temporary compressed folder and prompts them to extract first.
2. **Python Runtime Detection & Bootstrap**: Checks for existing `python` or `py -3` (>= 3.9). If missing, silently installs bundled `python-installer.exe` (Python 3.13 64-bit).
3. **Dependency Installation**: Runs `pip install -r requirements.txt` (installs PySide6).
4. **App Deployment**: Copies application files to `%LOCALAPPDATA%\MarkoPoloExplorer`.
5. **Shortcuts**: Executes an inline VBScript (`mpe_shortcut.vbs`) to generate shortcuts on Desktop and Start Menu with icon `markopolo.ico`.
6. **Auto-Start**: Immediately launches `run_app.bat`.

### Uninstallation (`Uninstall Marko Polo Explorer.bat`)
1. Prompts for confirmation.
2. Deletes Desktop link (`%USERPROFILE%\Desktop\Marko Polo Explorer.lnk`) and Start Menu link.
3. Deletes all program files inside `%LOCALAPPDATA%\MarkoPoloExplorer`.
4. Schedules self-deletion of the uninstaller batch file and install folder via `cmd /c timeout ... rmdir`.

---

## 7. Guidelines for Future AI Agents & Developers

When making modifications to Marko Polo Explorer:

1. **Always Maintain Code Sync**:
   - Primary application code lives in `image_capture_app.py` in the project root.
   - Run `python3 update_version.py` or `./BUILD_AND_PACKAGE.command` after editing `image_capture_app.py` so that changes propagate to `MAC/image_capture_app.py` and `WINDOWS/image_capture_app.py`.

2. **Cross-Platform Safety**:
   - Always wrap PyObjC imports or macOS-specific APIs in `try ... except ImportError` and check `HAS_PYOBJC` before invoking `ImageCaptureCore` calls.
   - Avoid hardcoded macOS paths (`/Users/...`) or Windows paths (`C:\...`) in core logic; use `os.path.join`, `Path.home()`, or Qt file dialogs.

3. **Versioning Rule**:
   - Do NOT manually edit version strings in python code. Run `python3 update_version.py` to auto-bump the timestamp.

4. **Web Server Deployment**:
   - Refer to `SERVER_UPLOAD_INSTRUCTIONS.md` when uploading new releases to `http://marko.com.hr/public_html/markopolo/`.
