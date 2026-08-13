# Marko Polo Explorer — Windows iPhone Detection Analysis & Implementation Guide

## Problem Summary
When running **Marko Polo Explorer** on **Windows 10/11**:
1. An Apple iPhone connected via USB (Lightning or USB-C) is recognized by Windows and can be browsed normally in **Windows File Explorer** (`This PC\Apple iPhone\Internal Storage\DCIM` or `This PC\Apple iPhone\Internal Storage\202603__a` etc.).
2. However, inside Marko Polo Explorer:
   - A black **cmd/powershell window** flashes or opens on the screen during device scanning.
   - After waiting, the script closes and the app reports **"No iPhone detected"**.

---

## Root Cause Analysis

### 1. Visible Console Window Popup (`cmd.exe` / `powershell.exe`)
- **Cause**: In `image_capture_app.py`, `subprocess.run(["powershell", ...])` is called without Windows-specific process creation flags.
- **Fix**: On Windows, pass `creationflags=subprocess.CREATE_NO_WINDOW` (`0x08000000`) and `startupinfo` to hide the window completely:
  ```python
  startupinfo = subprocess.STARTUPINFO()
  startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
  startupinfo.wShowWindow = 0  # SW_HIDE
  flags = 0x08000000          # CREATE_NO_WINDOW

  subprocess.run(
      ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
      capture_output=True,
      text=True,
      timeout=30,
      startupinfo=startupinfo,
      creationflags=flags
  )
  ```

---

### 2. Why Windows Shell COM (`Shell.Application`) Failed / Timed Out on iPhone WPD
Windows exposes the iPhone as a **Windows Portable Device (WPD)** rather than a standard drive letter (like `C:` or `D:`).

When accessing WPD devices via PowerShell's `Shell.Application`:
- **Apartment Threading (STA vs MTA)**: `Shell.Application` COM requires an **STA (Single-Threaded Apartment)**. In non-interactive PowerShell subprocesses, COM calls on Shell items can deadlock, block, or fail silently without a pumped message loop.
- **Shell Namespace Enumeration**: `$thisPC = $shell.NameSpace(17)` (ssfDRIVES). On some Windows 11 builds, WPD devices are not direct children of `17` or require recursive parsing through `This PC` (`shell:MyComputerFolder` or `::{20D04FE0-3AEA-1069-A2D8-08002B30309D}`).
- **Deep Item Hierarchy**: An iPhone's storage structure is:
  `This PC` ➔ `Apple iPhone` ➔ `Internal Storage` ➔ `DCIM` ➔ Folders (`100APPLE`, `202603__a`, etc.) ➔ Media Files.
  Recursive COM traversal in PowerShell on large photo libraries (thousands of photos) times out and blocks.

---

## Recommended Robust Solutions for Future AI / Developers

### Option A (Recommended): Native C++/C# Windows WPD Helper (`wpd_helper.exe`)
Compile a lightweight, standalone Windows helper binary (or C# script via `Add-Type` / `csc.exe`) using the official **Windows Portable Devices (WPD) API**:
- Headers: `<portabledeviceapi.h>`, `<portabledevice.h>`
- Interfaces:
  - `IPortableDeviceManager::GetDevices()` — Instantly lists all connected WPD devices (Apple iPhone, Android, cameras).
  - `IPortableDeviceContent::EnumObjects()` — Rapidly lists all object IDs and properties (name, size, MIME type).
  - `IPortableDeviceResources::GetStream()` — Fast streaming/copying of media files directly to disk without Shell COM overhead.

### Option B: PowerShell with STA Mode & Direct WPD Automation
If using PowerShell, run with `-Sta` flag and target the device name directly:
```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Sta -Command "
$shell = New-Object -ComObject Shell.Application
$thisPC = $shell.NameSpace('shell:MyComputerFolder')
$iphone = $thisPC.Items() | Where-Object { $_.Name -match 'iPhone|Apple' } | Select-Object -First 1
if ($iphone) {
    # Process Internal Storage
    $storage = $iphone.GetFolder.Items() | Where-Object { $_.Name -match 'Internal Storage|Storage' } | Select-Object -First 1
    # Enumerate folders
}
"
```

### Option C: `libimobiledevice` / `usbmuxd` for Windows
Use pre-compiled `libimobiledevice` (and `ideviceimagemounter` / `ifuse` / `afc`) for Windows:
- Direct, high-speed Apple Native Protocol access over USB lightning.
- Bypasses Windows Explorer & WPD entirely.

---

## Key Files in this Codebase
- **`image_capture_app.py`**:
  - `WindowsWPDCameraFile`: Lines ~460–480 (Data model for Windows camera files).
  - `WindowsWPDScanWorker`: Lines ~482–580 (`QThread` for background scanning).
  - `_start_device_scanning()`: Lines ~8100–8130 (Platform-aware device scan dispatcher).
  - `_download_windows_wpd_file()`: Lines ~8510–8560 (File transfer routine for Windows).
- **`.github/workflows/build-windows.yml`**: GitHub Actions automated PyInstaller build pipeline.
