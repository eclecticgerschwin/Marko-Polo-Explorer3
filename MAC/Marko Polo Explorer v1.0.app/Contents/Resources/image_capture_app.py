#!/usr/bin/env python3
"""
Marko Polo Explorer
"""
import sys
import os
import tempfile
import shutil
import random
import json
import re
import platform
import time
import subprocess
from pathlib import Path
from datetime import datetime
import traceback
try:
    import shiboken6 as shiboken
except ImportError:
    shiboken = None

class Tee:
    def __init__(self, original_stream, file_path):
        self.original_stream = original_stream
        try:
            self.file = open(file_path, "a", encoding="utf-8", buffering=1)
        except Exception:
            self.file = None
        
    def write(self, data):
        if self.original_stream:
            try:
                self.original_stream.write(data)
                self.original_stream.flush()
            except Exception:
                pass
        if self.file:
            try:
                self.file.write(data)
                self.file.flush()
                os.fsync(self.file.fileno())
            except Exception:
                pass
                
    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass
        if self.file:
            try:
                self.file.flush()
            except Exception:
                pass

script_dir = os.path.dirname(os.path.abspath(__file__))
stdout_log = os.path.join(script_dir, "app_stdout.log")
stderr_log = os.path.join(script_dir, "app_stderr.log")

def get_asset_path(filename):
    p = os.path.join(script_dir, filename)
    if os.path.exists(p):
        return p
    p2 = os.path.join(os.getcwd(), filename)
    if os.path.exists(p2):
        return p2
    return filename

sys.stdout = Tee(sys.stdout, stdout_log)
sys.stderr = Tee(sys.stderr, stderr_log)

def exception_logger(etype, value, tb):
    try:
        log_path = os.path.join(script_dir, "app_crash_log.txt")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n" + "="*60 + "\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Exception Type: {etype.__name__ if hasattr(etype, '__name__') else etype}\n")
            f.write(f"Exception Value: {value}\n")
            f.write("Traceback:\n")
            traceback.print_exception(etype, value, tb, file=f)
            f.write("="*60 + "\n")
    except Exception as e:
        pass
    sys.__excepthook__(etype, value, tb)

sys.excepthook = exception_logger

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFileDialog, QScrollArea, QFrame, QSplitter,
    QProgressBar, QComboBox, QLineEdit, QGridLayout, QMessageBox, QSizePolicy,
    QInputDialog, QMenu, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSlider, QTextEdit, QDialog, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRotation
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QSize, QPoint, QRunnable, QThreadPool, QObject, Slot, QMimeData, QRect, QEvent, QUrl,
    QItemSelection, QItemSelectionModel, QPropertyAnimation, QEasingCurve, Property
)
from PySide6.QtGui import (
    QPixmap, QColor, QPainter, QFont, QIcon, QPen, QBrush, QImage, QImageReader, QDesktopServices,
    QDrag, QDropEvent, QDragEnterEvent, QAction, QCursor, QLinearGradient, QMovie,
    QVector3D, QGuiApplication
)

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
    HAS_QT_MULTIMEDIA = True
except ImportError:
    HAS_QT_MULTIMEDIA = False

# Try importing PyObjC and ImageCaptureCore
try:
    import objc
    from Foundation import NSObject, NSURL, NSDictionary, NSBundle
    from ImageCaptureCore import (
        ICDeviceBrowser, ICCameraDevice, ICCameraFile,
        ICDeviceTypeMaskCamera, ICDeviceLocationTypeMaskLocal,
        ICDeviceLocationTypeMaskShared, ICDeviceLocationTypeMaskBonjour,
        ICDeviceLocationTypeMaskBluetooth, ICDeviceLocationTypeMaskRemote,
        ICDownloadsDirectoryURL, ICOverwrite
    )
    HAS_PYOBJC = True
except ImportError:
    HAS_PYOBJC = False

import urllib.request
import urllib.parse
import zipfile

__version__ = "13082621"
DEFAULT_UPDATE_CHECK_URL = "http://marko.com.hr/markopolo/version.json"


class CheckUpdateThread(QThread):
    update_found = Signal(dict)
    no_update = Signal()
    check_failed = Signal(str)

    def __init__(self, check_url=None, current_version=__version__):
        super().__init__()
        self.check_url = check_url or DEFAULT_UPDATE_CHECK_URL
        self.current_version = current_version

    def run(self):
        try:
            req = urllib.request.Request(self.check_url, headers={'User-Agent': 'MarkoPoloExplorer/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    remote_ver = data.get("version", "0.0.0")
                    if self._is_newer(remote_ver, self.current_version):
                        self.update_found.emit(data)
                        return
            self.no_update.emit()
        except Exception as e:
            self.check_failed.emit(str(e))

    def _is_newer(self, remote, local):
        def parse(v):
            return [int(x) for x in re.sub(r'[^0-9.]', '', str(v)).split('.') if x.isdigit()]
        try:
            return parse(remote) > parse(local)
        except Exception:
            return False


class DownloadUpdateThread(QThread):
    progress_signal = Signal(int, int) # downloaded, total
    download_finished = Signal(str)    # path to downloaded zip file
    download_failed = Signal(str)

    def __init__(self, download_url):
        super().__init__()
        self.download_url = download_url

    def run(self):
        try:
            tmp_zip = os.path.join(tempfile.gettempdir(), f"markopolo_update_{os.getpid()}.zip")
            req = urllib.request.Request(self.download_url, headers={'User-Agent': 'MarkoPoloExplorer/1.0'})
            with urllib.request.urlopen(req, timeout=45) as response, open(tmp_zip, 'wb') as out_file:
                total_length = response.headers.get('content-length')
                total_bytes = int(total_length) if total_length else 0
                downloaded = 0
                block_size = 16384
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    out_file.write(buffer)
                    self.progress_signal.emit(downloaded, total_bytes)
            self.download_finished.emit(tmp_zip)
        except Exception as e:
            self.download_failed.emit(str(e))

# ── Custom Confirmation Dialog Helper (Uses markopolo.png App Icon) ──────────────
def ask_user_confirmation(parent, title, text, buttons=QMessageBox.Yes | QMessageBox.No, default_button=QMessageBox.Yes):
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStandardButtons(buttons)
    msg_box.setDefaultButton(default_button)
    
    msg_box.setStyleSheet("""
        QMessageBox, QDialog {
            background-color: #ffffff;
            color: #000000;
        }
        QLabel {
            color: #000000;
            font-size: 13px;
            font-weight: 600;
        }
        QPushButton {
            background-color: #0a84ff;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 6px 18px;
            font-weight: bold;
            font-size: 12px;
            min-width: 65px;
        }
        QPushButton:hover {
            background-color: #0071e3;
        }
    """)
    
    markopolo_path = os.path.join(script_dir, "markopolo.png")
    if os.path.exists(markopolo_path):
        pix = QPixmap(markopolo_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        msg_box.setIconPixmap(pix)
        
    return msg_box.exec()

# ── Palette & Theming ────────────────────────────────────────────────────────
DARK_THEME = {
    "BG":       "#121212",
    "PANEL_BG": "#1a1a1a",
    "HEADER":   "#0d0d0d",
    "ACCENT":   "#0a84ff",
    "ACCENT2":  "#30c7ff",
    "BORDER":   "#2a2a2a",
    "TEXT":     "#f0f0f0",
    "SUBTEXT":  "#a1a1aa",
    "DOT_DONE":    "#30d158",
    "DOT_PENDING": "#ff453a",
    "DOT_COPY":    "#ff9f0a",
    # Secondary UI colors (previously hardcoded inline)
    "CARD_BG":       "#0d0d0d",
    "INPUT_BG":      "#1e1e1e",
    "HOVER_BG":      "#222222",
    "BTN_BG":        "#2a2a2a",
    "BTN_HOVER":     "#3a3a3a",
    "BTN_PRESSED":   "#1a1a1a",
    "SCROLLBAR_HANDLE": "#444",
    "HDR_LEFT_GRAD": "#1e1b4b",
    "HDR_RIGHT_GRAD": "#2b2b2b",
    "TITLE_COLOR":   "white",
    "PREVIEW_BG":    "#0d0d0d",
}

LIGHT_THEME = {
    "BG":       "#f0f2f5",
    "PANEL_BG": "#ffffff",
    "HEADER":   "#ffffff",
    "ACCENT":   "#0a84ff",
    "ACCENT2":  "#30c7ff",
    "BORDER":   "#d1d5db",
    "TEXT":     "#111827",
    "SUBTEXT":  "#4b5563",
    "DOT_DONE":    "#30d158",
    "DOT_PENDING": "#ff453a",
    "DOT_COPY":    "#ff9f0a",
    # Secondary UI colors for light mode
    "CARD_BG":       "#f8fafc",
    "INPUT_BG":      "#f1f5f9",
    "HOVER_BG":      "#f1f5f9",
    "BTN_BG":        "#f1f5f9",
    "BTN_HOVER":     "#e2e8f0",
    "BTN_PRESSED":   "#cbd5e1",
    "SCROLLBAR_HANDLE": "#cbd5e1",
    "HDR_LEFT_GRAD": "#eef2ff",
    "HDR_RIGHT_GRAD": "#ffffff",
    "TITLE_COLOR":   "#111827",
    "PREVIEW_BG":    "#f8fafc",
}

CURRENT_THEME_MODE = "light"

def set_theme(mode="light"):
    """Update all global color constants to match the selected theme."""
    global BG, PANEL_BG, HEADER, ACCENT, ACCENT2, BORDER, TEXT, SUBTEXT
    global DOT_DONE, DOT_PENDING, DOT_COPY
    global CARD_BG, INPUT_BG, HOVER_BG, BTN_BG, BTN_HOVER, BTN_PRESSED
    global SCROLLBAR_HANDLE, HDR_LEFT_GRAD, HDR_RIGHT_GRAD, TITLE_COLOR, PREVIEW_BG
    global CURRENT_THEME_MODE
    CURRENT_THEME_MODE = mode
    theme = DARK_THEME if mode == "dark" else LIGHT_THEME
    BG       = theme["BG"]
    PANEL_BG = theme["PANEL_BG"]
    HEADER   = theme["HEADER"]
    ACCENT   = theme["ACCENT"]
    ACCENT2  = theme["ACCENT2"]
    BORDER   = theme["BORDER"]
    TEXT     = theme["TEXT"]
    SUBTEXT  = theme["SUBTEXT"]
    DOT_DONE    = theme["DOT_DONE"]
    DOT_PENDING = theme["DOT_PENDING"]
    DOT_COPY    = theme["DOT_COPY"]
    CARD_BG       = theme["CARD_BG"]
    INPUT_BG      = theme["INPUT_BG"]
    HOVER_BG      = theme["HOVER_BG"]
    BTN_BG        = theme["BTN_BG"]
    BTN_HOVER     = theme["BTN_HOVER"]
    BTN_PRESSED   = theme["BTN_PRESSED"]
    SCROLLBAR_HANDLE = theme["SCROLLBAR_HANDLE"]
    HDR_LEFT_GRAD = theme["HDR_LEFT_GRAD"]
    HDR_RIGHT_GRAD = theme["HDR_RIGHT_GRAD"]
    TITLE_COLOR   = theme["TITLE_COLOR"]
    PREVIEW_BG    = theme["PREVIEW_BG"]

# Initialize with light theme
set_theme("light")

EXTS = {".jpg",".jpeg",".png",".heic",".heif",".tif",".tiff",
        ".gif",".bmp",".webp",".raw",".cr2",".nef",".arw",".dng",
        ".mp4",".mov",".avi",".mkv",".m4v"}

VIDEO_EXTS = {".mp4",".mov",".avi",".mkv",".m4v"}

THUMB_SIZE = 140
GRID_PAD   = 8

# ── Size Formatter ───────────────────────────────────────────────────────────
def format_size(bytes_val):
    if bytes_val is None or bytes_val < 0: return ""
    v = float(bytes_val)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if v < 1024.0:
            return f"{v:.1f} {unit}"
        v /= 1024.0
    return f"{v:.1f} TB"

# ── EXIF GPS & Reverse Geocoding Helper Functions ─────────────────────────────
_GPS_CACHE = {}

def extract_image_exif_gps(image_path):
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        from PIL import Image, ExifTags
        img = Image.open(image_path)
        exif = img._getexif()
        if not exif:
            return None
        gps_info = {}
        for key, val in exif.items():
            tag_name = ExifTags.TAGS.get(key, key)
            if tag_name == "GPSInfo":
                for g_key in val:
                    g_name = ExifTags.GPSTAGS.get(g_key, g_key)
                    gps_info[g_name] = val[g_key]
                break
        if not gps_info:
            return None
        lat_data = gps_info.get("GPSLatitude")
        lat_ref = gps_info.get("GPSLatitudeRef")
        lon_data = gps_info.get("GPSLongitude")
        lon_ref = gps_info.get("GPSLongitudeRef")
        if not lat_data or not lon_data or not lat_ref or not lon_ref:
            return None
            
        def convert_to_degrees(value):
            try:
                d = float(value[0])
                m = float(value[1])
                s = float(value[2])
                return d + (m / 60.0) + (s / 3600.0)
            except Exception:
                return float(value)
                
        lat = convert_to_degrees(lat_data)
        if str(lat_ref).upper() != 'N': lat = -lat
        lon = convert_to_degrees(lon_data)
        if str(lon_ref).upper() != 'E': lon = -lon
        return lat, lon
    except Exception:
        return None

def get_location_name_from_coords(lat, lon):
    cache_key = (round(lat, 3), round(lon, 3))
    if cache_key in _GPS_CACHE:
        return _GPS_CACHE[cache_key]
    try:
        import urllib.request, json
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&zoom=10"
        req = urllib.request.Request(url, headers={'User-Agent': 'MarkoPoloExplorer/1.0'})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            addr = data.get("address", {})
            country = addr.get("country", "")
            state = addr.get("state") or addr.get("region") or addr.get("county") or ""
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality") or ""
            parts = [p for p in [city, state, country] if p]
            if parts:
                loc_str = ", ".join(parts)
                _GPS_CACHE[cache_key] = loc_str
                return loc_str
    except Exception:
        pass
    loc_str = f"{lat:.4f}°, {lon:.4f}°"
    _GPS_CACHE[cache_key] = loc_str
    return loc_str

# ── Simulated Camera File for Demo Mode ──────────────────────────────────────
class SimulatedCameraFile:
    def __init__(self, name, size):
        self._name = name
        self._size = size
        # Mock creation date for list view
        self._creation = datetime.now()

    def name(self):
        return self._name

    def fileSize(self):
        return self._size

    def creationDate(self):
        return self._creation

    def thumbnailData(self):
        return None  # Fall back to extension-based visuals

# ── Android Camera File Representation ───────────────────────────────────────
class AndroidCameraFile:
    def __init__(self, name, size, remote_path=None, serial=None, is_simulated=False):
        self._name = name
        self._size = size
        self.remote_path = remote_path
        self.serial = serial
        self.is_simulated = is_simulated
        self._creation = datetime.now()

    def name(self):
        return self._name

    def fileSize(self):
        return self._size

    def creationDate(self):
        return self._creation

    def thumbnailData(self):
        return None

# ── Windows WPD (Apple iPhone / Portable Device) Representation ───────────────
class WindowsWPDCameraFile:
    def __init__(self, name, size=0, folder="", device_name="Apple iPhone", is_simulated=False):
        self._name = name
        self._size = size
        self.folder = folder
        self.device_name = device_name
        self.is_simulated = is_simulated
        self._creation = datetime.now()

    def name(self):
        return self._name

    def fileSize(self):
        return self._size

    def creationDate(self):
        return self._creation

    def thumbnailData(self):
        return None

class WindowsWPDScanWorker(QThread):
    scan_complete = Signal(str, list)
    scan_error = Signal(str)

    def __init__(self, target_device=None, parent=None):
        super().__init__(parent)
        self.target_device = target_device

    def run(self):
        ps_script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$shell = New-Object -ComObject Shell.Application
$thisPC = $shell.NameSpace(17)
$dev = $null
if ($thisPC) {
    foreach ($item in $thisPC.Items()) {
        if ($item.Name -match "iPhone|Apple|iPad|Portable|Camera") {
            $dev = $item
            break
        }
    }
}

if (-not $dev) {
    Write-Output "[]"
    exit
}

$devName = $dev.Name
$files = @()

function Scan-FolderItems($folder, $depth) {
    if ($depth -gt 6) { return }
    $items = $folder.Items()
    if (-not $items) { return }
    foreach ($it in $items) {
        if ($it.IsFolder) {
            Scan-FolderItems $it.GetFolder ($depth + 1)
        } else {
            $fn = $it.Name
            $ext = [System.IO.Path]::GetExtension($fn).ToLower()
            if ($ext -match "\.(jpg|jpeg|png|heic|mov|mp4|dng|raw|arw|m4v|gif|webp|avi)$") {
                $sz = 0
                try { $sz = [int64]$it.Size } catch {}
                if ($sz -le 0) {
                    try {
                        $szStr = $folder.GetDetailsOf($it, 1)
                        if ($szStr -match "([\d\.\,]+)\s*(KB|MB|GB|B)?") {
                            $num = [double]($matches[1] -replace ",","")
                            $unit = $matches[2]
                            if ($unit -eq "KB") { $sz = [int64]($num * 1024) }
                            elseif ($unit -eq "MB") { $sz = [int64]($num * 1024 * 1024) }
                            elseif ($unit -eq "GB") { $sz = [int64]($num * 1024 * 1024 * 1024) }
                            else { $sz = [int64]$num }
                        }
                    } catch {}
                }
                $files += [PSCustomObject]@{
                    name = $fn
                    size = $sz
                    folder = $folder.Title
                    device = $devName
                }
            }
        }
    }
}

Scan-FolderItems $dev.GetFolder 0
$files | ConvertTo-Json -Compress
"""
        try:
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            stdout = res.stdout.strip()
            if not stdout or stdout == "[]":
                self.scan_complete.emit("", [])
                return
            data = json.loads(stdout)
            if isinstance(data, dict):
                data = [data]
            wpd_files = []
            device_name = "Apple iPhone"
            for item in data:
                fn = item.get("name", "")
                sz = int(item.get("size", 0))
                folder = item.get("folder", "")
                device_name = item.get("device", device_name)
                if fn:
                    wpd_files.append(WindowsWPDCameraFile(fn, sz, folder=folder, device_name=device_name))
            self.scan_complete.emit(device_name, wpd_files)
        except Exception as e:
            self.scan_error.emit(str(e))

# ── PyObjC Delegates ─────────────────────────────────────────────────────────
if HAS_PYOBJC:
    class DeviceBrowserDelegate(NSObject):
        def initWithParent_(self, parent):
            self = objc.super(DeviceBrowserDelegate, self).init()
            if self is None: return None
            self.parent = parent
            return self

        def deviceBrowser_didAddDevice_moreComing_(self, browser, device, moreComing):
            self.parent.device_found_signal.emit(device)

        def deviceBrowser_didRemoveDevice_moreGoing_(self, browser, device, moreGoing):
            self.parent.device_removed_signal.emit(device)

        def deviceBrowser_didRemoveDevice_moreComing_(self, browser, device, moreComing):
            self.parent.device_removed_signal.emit(device)

    class CameraDeviceDelegate(NSObject):
        def initWithParent_(self, parent):
            self = objc.super(CameraDeviceDelegate, self).init()
            if self is None: return None
            self.parent = parent
            return self

        def cameraDevice_didAddItems_(self, camera, items):
            self.parent.items_added_signal.emit(items)

        def device_didOpenSessionWithError_(self, device, error):
            self.parent.session_opened_signal.emit(device, error)

        def device_didCloseSessionWithError_(self, device, error):
            self.parent.session_closed_signal.emit(device, error)

        def deviceDidBecomeReady_(self, device):
            self.parent.device_ready_signal.emit(device)

        def deviceDidBecomeReadyWithCompleteContentCatalog_(self, device):
            self.parent.device_ready_signal.emit(device)

        def didRemoveDevice_(self, device):
            self.parent.device_removed_signal.emit(device)

        def device_didEncounterError_(self, device, error):
            pass

        def deviceDidChangeName_(self, device):
            pass

        def deviceDidChangeSharingState_(self, device):
            pass

        def device_didReceiveStatusInformation_(self, device, status):
            pass

    class CameraDownloadDelegate(NSObject):
        def initWithParent_(self, parent):
            self = objc.super(CameraDownloadDelegate, self).init()
            if self is None: return None
            self.parent = parent
            return self

        def didDownloadFile_error_options_contextInfo_(self, file, error, options, contextInfo):
            file_name = str(file.name()) if file else ""
            error_msg = str(error.localizedDescription()) if error else None
            self.parent.file_downloaded_signal.emit(file_name, error_msg)

# ── Controller/Manager ────────────────────────────────────────────────────────
class ImageCaptureManager(QObject):
    device_found_signal = Signal(object)
    device_removed_signal = Signal(object)
    items_added_signal = Signal(object)
    session_opened_signal = Signal(object, object)
    session_closed_signal = Signal(object, object)
    device_ready_signal = Signal(object)
    file_downloaded_signal = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.browser = None
        self.browser_delegate = None
        self.camera_delegate = None
        self.download_delegate = None
        self.active_camera = None

    def start_scanning(self):
        if not HAS_PYOBJC: return
        self.browser = ICDeviceBrowser.alloc().init()
        self.browser_delegate = DeviceBrowserDelegate.alloc().initWithParent_(self)
        self.browser.setDelegate_(self.browser_delegate)
        # Combine camera type and location type masks
        mask = (
            ICDeviceTypeMaskCamera |
            ICDeviceLocationTypeMaskLocal |
            ICDeviceLocationTypeMaskShared |
            ICDeviceLocationTypeMaskBonjour |
            ICDeviceLocationTypeMaskBluetooth |
            ICDeviceLocationTypeMaskRemote
        )
        self.browser.setBrowsedDeviceTypeMask_(mask)
        self.browser.start()

    def stop_scanning(self):
        if self.browser:
            self.browser.stop()
            self.browser = None
        self.close_camera_session()

    def open_camera_session(self, camera_device):
        if not HAS_PYOBJC: return
        if self.active_camera:
            self.close_camera_session()
        self.active_camera = camera_device
        self.camera_delegate = CameraDeviceDelegate.alloc().initWithParent_(self)
        self.active_camera.setDelegate_(self.camera_delegate)
        self.active_camera.requestOpenSession()

    def close_camera_session(self):
        if self.active_camera:
            self.active_camera.requestCloseSession()
            self.active_camera = None
            self.camera_delegate = None

    def download_file(self, file_object, destination_path):
        if not HAS_PYOBJC or not self.active_camera: return
        if not self.download_delegate:
            self.download_delegate = CameraDownloadDelegate.alloc().initWithParent_(self)

        dest_url = NSURL.fileURLWithPath_(destination_path)
        options = {
            ICDownloadsDirectoryURL: dest_url,
            ICOverwrite: True
        }
        self.active_camera.requestDownloadFile_options_downloadDelegate_didDownloadSelector_contextInfo_(
            file_object,
            options,
            self.download_delegate,
            "didDownloadFile:error:options:contextInfo:",
            None
        )

# ── Native Video Player Preview Widget ─────────────────────────────────────────
class NativeVideoPlayerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        
        self.video_widget = QVideoWidget(self)
        self.player.setVideoOutput(self.video_widget)
        
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(4)
        main_lay.addWidget(self.video_widget, 1)
        
        glass_btn_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.12);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.25);
                border-color: rgba(255, 255, 255, 0.4);
            }
            QPushButton:pressed {
                background: rgba(10, 132, 255, 0.5);
            }
        """

        glass_slider_style = """
            QSlider::groove:horizontal {
                border: 1px solid rgba(255, 255, 255, 0.2);
                height: 5px;
                background: rgba(255, 255, 255, 0.12);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.4);
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #0a84ff;
            }
        """

        # Timeline layout
        time_lay = QHBoxLayout()
        time_lay.setContentsMargins(4, 0, 4, 0)
        time_lay.setSpacing(6)
        
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setCursor(Qt.PointingHandCursor)
        self.timeline_slider.setStyleSheet(glass_slider_style)
        self.timeline_slider.sliderMoved.connect(self._on_slider_seek)
        
        self.time_lbl = QLabel("00:00 / 00:00")
        self.time_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.85); font-size:10px; font-weight:bold;")
        
        time_lay.addWidget(self.timeline_slider, 1)
        time_lay.addWidget(self.time_lbl)
        main_lay.addLayout(time_lay)
        
        # Controls Bar (Play/Pause centered & rounded, Stop, Mute, Volume Slider) - Centered with Glassmorphism
        ctrl_lay = QHBoxLayout()
        ctrl_lay.setContentsMargins(4, 2, 4, 4)
        ctrl_lay.setSpacing(8)
        
        round_play_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.18);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.35);
                border-radius: 17px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.32);
                border-color: rgba(255, 255, 255, 0.55);
            }
            QPushButton:pressed {
                background: rgba(10, 132, 255, 0.6);
            }
        """

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(34, 34)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setStyleSheet(round_play_style)
        self.play_btn.setToolTip("Play / Pause")
        self.play_btn.clicked.connect(self.toggle_play)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setStyleSheet(glass_btn_style)
        self.stop_btn.clicked.connect(self.stop_video)
        
        self.mute_btn = QPushButton("🔊 Mute")
        self.mute_btn.setCursor(Qt.PointingHandCursor)
        self.mute_btn.setStyleSheet(glass_btn_style)
        self.mute_btn.clicked.connect(self.toggle_mute)
        
        # Volume Control Slider
        self.vol_lbl = QLabel("🔊")
        self.vol_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.85); font-size: 11px;")
        
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(65)
        self.vol_slider.setCursor(Qt.PointingHandCursor)
        self.vol_slider.setStyleSheet(glass_slider_style)
        self.vol_slider.setToolTip("Volume level")
        self.vol_slider.valueChanged.connect(self._on_volume_changed)

        self.audio_output.setVolume(0.8)

        ctrl_lay.addStretch(1)
        ctrl_lay.addWidget(self.stop_btn)
        ctrl_lay.addSpacing(6)
        ctrl_lay.addWidget(self.play_btn)
        ctrl_lay.addSpacing(6)
        ctrl_lay.addWidget(self.mute_btn)
        ctrl_lay.addWidget(self.vol_lbl)
        ctrl_lay.addWidget(self.vol_slider)
        ctrl_lay.addStretch(1)
        main_lay.addLayout(ctrl_lay)
        
        self.player.positionChanged.connect(self._on_pos_changed)
        self.player.durationChanged.connect(self._on_dur_changed)

    def load_video(self, file_path):
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()
        self.play_btn.setText("⏸")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_btn.setText("▶")
        else:
            self.player.play()
            self.play_btn.setText("⏸")

    def stop_video(self):
        self.player.stop()
        self.play_btn.setText("▶")

    def toggle_mute(self):
        is_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(not is_muted)
        self.mute_btn.setText("🔇 Unmute" if not is_muted else "🔊 Mute")

    def _on_volume_changed(self, val):
        vol = val / 100.0
        self.audio_output.setVolume(vol)
        if val == 0:
            self.audio_output.setMuted(True)
            self.mute_btn.setText("🔇 Muted")
        else:
            self.audio_output.setMuted(False)
            self.mute_btn.setText("🔊 Mute")

    def seek_relative(self, ms_offset):
        if self.player.duration() > 0:
            new_pos = max(0, min(self.player.duration(), self.player.position() + ms_offset))
            self.player.setPosition(new_pos)

    def _on_slider_seek(self, pos):
        if self.player.duration() > 0:
            target_ms = int((pos / 1000.0) * self.player.duration())
            self.player.setPosition(target_ms)

    def _on_pos_changed(self, pos):
        if not self.timeline_slider.isSliderDown() and self.player.duration() > 0:
            val = int((pos / float(self.player.duration())) * 1000)
            self.timeline_slider.setValue(val)
        self._update_time(pos, self.player.duration())

    def _on_dur_changed(self, dur):
        self._update_time(self.player.position(), dur)

    def _update_time(self, pos, dur):
        def fmt(ms):
            s = int(ms / 1000)
            m = s // 60
            s = s % 60
            return f"{m:02d}:{s:02d}"
        self.time_lbl.setText(f"{fmt(pos)} / {fmt(dur)}")

# ── Async Geocoding Thread for Instant Preview Navigation ─────────────────────
class AsyncLocationThread(QThread):
    location_ready = Signal(str, str)

    def __init__(self, path, lat, lon):
        super().__init__()
        self.path = path
        self.lat = lat
        self.lon = lon

    def run(self):
        try:
            loc_str = get_location_name_from_coords(self.lat, self.lon)
            self.location_ready.emit(self.path, f"📍 Location: {loc_str} ({self.lat:.4f}°, {self.lon:.4f}°)")
        except Exception:
            pass


# ── WASD D-Pad Keyboard Widget ────────────────────────────────────────────────
class WasdKeypadWidget(QWidget):
    """WASD Keyboard D-Pad widget for image preview navigation & zoom control."""
    def __init__(self, parent_dialog=None):
        super().__init__(parent_dialog)
        self.dialog = parent_dialog

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)

        self._default_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2c2c32, stop:1 #1c1c20);
                color: #e2e8f0;
                border: 1px solid #3a3a42;
                border-bottom: 2px solid #141418;
                border-radius: 3px;
                font-family: 'SF Mono', Consolas, monospace;
                font-size: 9px;
                font-weight: 800;
                min-width: 18px;
                max-width: 20px;
                min-height: 16px;
                max-height: 18px;
            }
            QPushButton:hover {
                background: #0a84ff;
                color: #ffffff;
                border-color: #30c7ff;
            }
            QPushButton:pressed {
                background: #0055d4;
                border-bottom-width: 1px;
            }
        """

        self.btn_w = QPushButton("W")
        self.btn_w.setStyleSheet(self._default_style)
        self.btn_w.setToolTip("W: Zoom In (➕)")
        self.btn_w.setCursor(Qt.PointingHandCursor)

        self.btn_a = QPushButton("A")
        self.btn_a.setStyleSheet(self._default_style)
        self.btn_a.setToolTip("A: Previous Image (◀)")
        self.btn_a.setCursor(Qt.PointingHandCursor)

        self.btn_s = QPushButton("S")
        self.btn_s.setStyleSheet(self._default_style)
        self.btn_s.setToolTip("S: Zoom Out (➖)")
        self.btn_s.setCursor(Qt.PointingHandCursor)

        self.btn_d = QPushButton("D")
        self.btn_d.setStyleSheet(self._default_style)
        self.btn_d.setToolTip("D: Next Image (▶)")
        self.btn_d.setCursor(Qt.PointingHandCursor)

        # WASD Layout: W on top over S, A on left, D on right
        grid.addWidget(self.btn_w, 0, 1)
        grid.addWidget(self.btn_a, 1, 0)
        grid.addWidget(self.btn_s, 1, 1)
        grid.addWidget(self.btn_d, 1, 2)

        # Connect button click signals
        self.btn_w.clicked.connect(self._on_click_w)
        self.btn_a.clicked.connect(self._on_click_a)
        self.btn_s.clicked.connect(self._on_click_s)
        self.btn_d.clicked.connect(self._on_click_d)

    def trigger_key_feedback(self, key_char):
        """Show action symbol (+, -, ◀, ▶) and press animation for 400ms when pressed or clicked."""
        k = str(key_char).upper()
        btn = None
        orig_text = k
        symbol = k

        if k in ("W", "+", "="):
            btn = self.btn_w
            orig_text = "W"
            symbol = "➕"
        elif k in ("A", "LEFT"):
            btn = self.btn_a
            orig_text = "A"
            symbol = "◀"
        elif k in ("S", "-"):
            btn = self.btn_s
            orig_text = "S"
            symbol = "➖"
        elif k in ("D", "RIGHT"):
            btn = self.btn_d
            orig_text = "D"
            symbol = "▶"

        if btn:
            btn.setText(symbol)
            btn.setStyleSheet("""
                QPushButton {
                    background: #0a84ff;
                    color: #ffffff;
                    border: 1px solid #30c7ff;
                    border-bottom: 2px solid #0055d4;
                    border-radius: 3px;
                    font-family: 'SF Mono', Consolas, monospace;
                    font-size: 10px;
                    font-weight: 800;
                    min-width: 18px;
                    max-width: 20px;
                    min-height: 16px;
                    max-height: 18px;
                }
            """)
            QTimer.singleShot(400, lambda b=btn, txt=orig_text: self._reset_btn(b, txt))

    def _reset_btn(self, btn, orig_text):
        btn.setText(orig_text)
        btn.setStyleSheet(self._default_style)

    def _on_click_w(self):
        self.trigger_key_feedback("W")
        if self.dialog and hasattr(self.dialog, "_zoom_in"):
            self.dialog._zoom_in()

    def _on_click_a(self):
        self.trigger_key_feedback("A")
        if self.dialog and hasattr(self.dialog, "_go_prev"):
            self.dialog._go_prev()

    def _on_click_s(self):
        self.trigger_key_feedback("S")
        if self.dialog and hasattr(self.dialog, "_zoom_out"):
            self.dialog._zoom_out()

    def _on_click_d(self):
        self.trigger_key_feedback("D")
        if self.dialog and hasattr(self.dialog, "_go_next"):
            self.dialog._go_next()


# ── Dark QuickLook Preview Dialog ─────────────────────────────────────────────
class DarkQuickLookDialog(QDialog):
    def __init__(self, file_list, start_index=0, parent=None):
        super().__init__(parent)
        self.file_list = file_list
        self.current_index = start_index if (0 <= start_index < len(file_list)) else 0
        self.zoom_factor = 1.0
        self.fit_mode = "fit"
        self._pix_cache = {}
        
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Quick Look - Marko Polo Explorer")
        self.resize(960, 680)
        self.setStyleSheet("""
            QDialog { background-color: #121212; color: #f0f0f0; }
            QLabel { background-color: #121212; color: #f0f0f0; }
            QPushButton {
                background: #1a1a1a;
                color: #f0f0f0;
                border: 1px solid #333333;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #0a84ff;
                color: white;
                border-color: #0a84ff;
            }
            QScrollArea, QScrollArea > QWidget > QWidget {
                background-color: #121212;
                border: none;
            }
            QScrollBar:vertical {
                background: #121212;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3a3a3c;
                min-height: 30px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #0a84ff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background: #121212;
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #3a3a3c;
                min-width: 30px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #0a84ff;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            QAbstractScrollArea::corner {
                background: #121212;
                border: none;
            }
        """)
        
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(8, 8, 8, 8)
        main_lay.setSpacing(8)
        
        # Upper Toolbar with Centered Main Title and Right-aligned Navigation
        tb_lay = QHBoxLayout()
        tb_lay.setSpacing(8)
        
        self.title_lbl = QLabel()
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #0a84ff;")

        # Zoom controls on LEFT side
        self.zoom_in_btn = QPushButton("🔍 +")
        self.zoom_in_btn.setToolTip("Zoom In (+)")
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        
        self.zoom_out_btn = QPushButton("🔍 -")
        self.zoom_out_btn.setToolTip("Zoom Out (-)")
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        
        self.fit_btn = QPushButton("🖼️ Fit Window")
        self.fit_btn.setToolTip("Resize image to fit window")
        self.fit_btn.clicked.connect(self._fit_to_window)
        
        self.actual_btn = QPushButton("1:1 Actual Size")
        self.actual_btn.setToolTip("View original 1:1 resolution")
        self.actual_btn.clicked.connect(self._actual_size)
        
        self.maximize_btn = QPushButton("⛶ Fullscreen")
        self.maximize_btn.setToolTip("Maximize / Toggle Fullscreen Preview")
        self.maximize_btn.clicked.connect(self._toggle_fullscreen)
        
        zoom_lay = QHBoxLayout()
        zoom_lay.setSpacing(6)
        zoom_lay.addWidget(self.zoom_in_btn)
        zoom_lay.addWidget(self.zoom_out_btn)
        zoom_lay.addWidget(self.fit_btn)
        zoom_lay.addWidget(self.actual_btn)
        zoom_lay.addWidget(self.maximize_btn)
        
        tb_lay.addLayout(zoom_lay)
        tb_lay.addWidget(self.title_lbl, 1)
        
        self.wasd_pad = WasdKeypadWidget(self)
        tb_lay.addWidget(self.wasd_pad)
        
        main_lay.addLayout(tb_lay)
        
        self._is_dragging = False
        self._drag_start_pos = QPoint()
        self._scroll_h_start = 0
        self._scroll_v_start = 0

        # Content Scroll Area & Stack
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("background-color: #121212; border: none;")
        self.scroll_area.viewport().setStyleSheet("background-color: #121212;")
        self.scroll_area.setContextMenuPolicy(Qt.CustomContextMenu)
        self.scroll_area.customContextMenuRequested.connect(self._show_preview_context_menu)
        self.scroll_area.installEventFilter(self)
        self.scroll_area.viewport().installEventFilter(self)
        
        self.img_lbl = QLabel()
        self.img_lbl.setStyleSheet("background-color: #121212;")
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.img_lbl.customContextMenuRequested.connect(self._show_preview_context_menu)
        self.img_lbl.installEventFilter(self)

        self.scroll_area.setWidget(self.img_lbl)
        self.scroll_area.setWidgetResizable(True)
        
        main_lay.addWidget(self.scroll_area, 1)
        
        # Video Player Widget
        if HAS_QT_MULTIMEDIA:
            self.video_player = NativeVideoPlayerWidget(self)
            self.video_player.hide()
            main_lay.addWidget(self.video_player, 1)
            
        # Text Preview Widget
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("background: #0d0d0d; color: #f0f0f0; border: 1px solid #2a2a2a; border-radius: 6px; font-family: monospace;")
        self.text_edit.hide()
        main_lay.addWidget(self.text_edit, 1)

        # Location & Metadata Bottom Banner for Big Preview Window
        self.location_lbl = QLabel()
        self.location_lbl.setAlignment(Qt.AlignCenter)
        self.location_lbl.setStyleSheet("""
            QLabel {
                background: transparent;
                color: #8e8e93;
                border: none;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 400;
            }
        """)
        self.location_lbl.hide()
        main_lay.addWidget(self.location_lbl)
        
        self.current_pixmap = None
        self._load_current_file()

    def _is_image_scrollable(self):
        """Check if the current zoomed image exceeds the scroll area viewport bounds."""
        if not hasattr(self, "scroll_area") or not self.scroll_area.isVisible() or not getattr(self, "current_pixmap", None):
            return False
        h_max = self.scroll_area.horizontalScrollBar().maximum()
        v_max = self.scroll_area.verticalScrollBar().maximum()
        return (h_max > 0 or v_max > 0 or getattr(self, "fit_mode", "fit") != "fit" or getattr(self, "zoom_factor", 1.0) > 1.0)

    def _update_cursor_mode(self):
        """Update cursor to OpenHandCursor when image is zoomed/scrollable."""
        if self._is_image_scrollable():
            if not getattr(self, "_is_dragging", False):
                self.img_lbl.setCursor(Qt.OpenHandCursor)
                self.scroll_area.viewport().setCursor(Qt.OpenHandCursor)
        else:
            self.img_lbl.setCursor(Qt.ArrowCursor)
            self.scroll_area.viewport().setCursor(Qt.ArrowCursor)

    def eventFilter(self, obj, event):
        if obj in (self.img_lbl, self.scroll_area, self.scroll_area.viewport()):
            # Handle Right Click Context Menu
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
                self._show_preview_context_menu(event.pos())
                return True

            # Handle Left Click Drag (Hand Pan) when zoomed in
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if self._is_image_scrollable():
                    self._is_dragging = True
                    self._drag_start_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                    self._scroll_h_start = self.scroll_area.horizontalScrollBar().value()
                    self._scroll_v_start = self.scroll_area.verticalScrollBar().value()
                    self.img_lbl.setCursor(Qt.ClosedHandCursor)
                    self.scroll_area.viewport().setCursor(Qt.ClosedHandCursor)
                    return True

            elif event.type() == QEvent.MouseMove:
                if getattr(self, "_is_dragging", False):
                    curr_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                    delta = curr_pos - self._drag_start_pos
                    self.scroll_area.horizontalScrollBar().setValue(self._scroll_h_start - delta.x())
                    self.scroll_area.verticalScrollBar().setValue(self._scroll_v_start - delta.y())
                    return True
                elif self._is_image_scrollable():
                    self.img_lbl.setCursor(Qt.OpenHandCursor)
                    self.scroll_area.viewport().setCursor(Qt.OpenHandCursor)

            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                if getattr(self, "_is_dragging", False):
                    self._is_dragging = False
                    self._update_cursor_mode()
                    return True

        return super().eventFilter(obj, event)

    def _show_preview_context_menu(self, pos):
        if not self.file_list or not (0 <= self.current_index < len(self.file_list)):
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2c2c2e;
                color: #ffffff;
                border: 1px solid #3a3a3c;
                padding: 4px;
                border-radius: 6px;
            }
            QMenu::item {
                padding: 6px 22px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QMenu::item:selected {
                background-color: #0a84ff;
                color: #ffffff;
            }
        """)

        copy_act = QAction("📋 Copy", self)
        cut_act = QAction("✂️ Cut", self)
        del_act = QAction("🗑️ Delete", self)

        menu.addAction(copy_act)
        menu.addAction(cut_act)
        menu.addSeparator()
        menu.addAction(del_act)

        selected_act = menu.exec(QCursor.pos())

        if selected_act == copy_act:
            self._copy_current_file()
        elif selected_act == cut_act:
            self._cut_current_file()
        elif selected_act == del_act:
            self._delete_current_file()

    def _copy_current_file(self):
        if not self.file_list or not (0 <= self.current_index < len(self.file_list)):
            return
        item = self.file_list[self.current_index]
        path = item if isinstance(item, str) else getattr(item, "path", str(item))
        if isinstance(path, str) and os.path.exists(path):
            cb = QApplication.clipboard()
            md = QMimeData()
            md.setUrls([QUrl.fromLocalFile(path)])
            cb.setMimeData(md)

    def _cut_current_file(self):
        self._copy_current_file()
        if self.parent() and hasattr(self.parent(), "cut_file_path"):
            item = self.file_list[self.current_index]
            path = item if isinstance(item, str) else getattr(item, "path", str(item))
            self.parent().cut_file_path = path

    def _delete_current_file(self):
        if not self.file_list or not (0 <= self.current_index < len(self.file_list)):
            return

        item = self.file_list[self.current_index]
        path = item if isinstance(item, str) else getattr(item, "path", str(item))
        filename = os.path.basename(path) if isinstance(path, str) else str(item)

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{filename}'?\n\nThis item will be moved to Trash / deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            if isinstance(path, str) and os.path.exists(path):
                if platform.system() == "Darwin":
                    os.system(f'osascript -e \'tell application "Finder" to delete POSIX file "{path}"\' >/dev/null 2>&1')
                    if os.path.exists(path):
                        os.remove(path)
                else:
                    os.remove(path)
        except Exception as ex:
            QMessageBox.warning(self, "Delete Error", f"Could not delete file:\n{ex}")

        del self.file_list[self.current_index]
        if not self.file_list:
            self.close()
        else:
            if self.current_index >= len(self.file_list):
                self.current_index = len(self.file_list) - 1
            self._load_current_file()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Left, Qt.Key_Up, Qt.Key_A):
            if hasattr(self, "wasd_pad"):
                self.wasd_pad.trigger_key_feedback("A")
            self._go_prev()
            e.accept()
        elif e.key() in (Qt.Key_Right, Qt.Key_Down, Qt.Key_D):
            if hasattr(self, "wasd_pad"):
                self.wasd_pad.trigger_key_feedback("D")
            self._go_next()
            e.accept()
        elif e.key() in (Qt.Key_Plus, Qt.Key_Equal, Qt.Key_W):
            if hasattr(self, "wasd_pad"):
                self.wasd_pad.trigger_key_feedback("W")
            self._zoom_in()
            e.accept()
        elif e.key() in (Qt.Key_Minus, Qt.Key_S):
            if hasattr(self, "wasd_pad"):
                self.wasd_pad.trigger_key_feedback("S")
            self._zoom_out()
            e.accept()
        elif e.key() == Qt.Key_Space or e.key() == Qt.Key_Escape:
            self.close()
            e.accept()
        elif e.key() == Qt.Key_Delete or e.key() == Qt.Key_Backspace:
            self._delete_current_file()
            e.accept()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e):
        self._sync_selection_to_panel()
        super().closeEvent(e)

    def _sync_selection_to_panel(self):
        if self.file_list and (0 <= self.current_index < len(self.file_list)):
            item = self.file_list[self.current_index]
            path_or_file = item if isinstance(item, str) else getattr(item, "path", str(item))
            if self.parent() and hasattr(self.parent(), "select_file_in_active_panel"):
                self.parent().select_file_in_active_panel(path_or_file)

    def wheelEvent(self, e):
        if self.scroll_area.isVisible() and self.current_pixmap:
            delta = e.angleDelta().y()
            if delta > 0:
                self._zoom_in()
            elif delta < 0:
                self._zoom_out()

    def _go_prev(self):
        if self.file_list and self.current_index > 0:
            self.current_index -= 1
            self._load_current_file()

    def _go_next(self):
        if self.file_list and self.current_index < len(self.file_list) - 1:
            self.current_index += 1
            self._load_current_file()

    def _load_current_file(self):
        if not self.file_list or not (0 <= self.current_index < len(self.file_list)):
            return
            
        item = self.file_list[self.current_index]
        path = item if isinstance(item, str) else getattr(item, "path", str(item))
        name = os.path.basename(path) if isinstance(path, str) else str(item)
        
        size_str = ""
        try:
            if isinstance(path, str) and os.path.exists(path):
                sz_bytes = os.path.getsize(path)
                size_str = f" ({format_size(sz_bytes)})"
            elif hasattr(item, "size"):
                size_str = f" ({format_size(item.size)})"
        except Exception:
            pass

        self.title_lbl.setText(f"[{self.current_index + 1} / {len(self.file_list)}]  {name}{size_str}")
        
        # Display Location (Instant folder path + Async EXIF GPS reverse-geocoding)
        if isinstance(path, str) and os.path.exists(path):
            folder_loc = os.path.dirname(os.path.abspath(path))
            self.location_lbl.setText(f"📁 Location: {folder_loc}")
            self.location_lbl.show()

            gps = extract_image_exif_gps(path)
            if gps:
                cache_key = (round(gps[0], 3), round(gps[1], 3))
                if cache_key in _GPS_CACHE:
                    loc_str = _GPS_CACHE[cache_key]
                    self.location_lbl.setText(f"📍 Location: {loc_str} ({gps[0]:.4f}°, {gps[1]:.4f}°)")
                else:
                    self._loc_thread = AsyncLocationThread(path, gps[0], gps[1])
                    self._loc_thread.location_ready.connect(self._on_location_ready)
                    self._loc_thread.start()
        else:
            self.location_lbl.hide()

        if hasattr(self, "video_player"):
            self.video_player.stop_video()
            self.video_player.hide()
        self.text_edit.hide()
        self.scroll_area.hide()
        
        ext = os.path.splitext(name)[1].lower() if isinstance(name, str) else ""
        
        if ext in VIDEO_EXTS and os.path.exists(path):
            if HAS_QT_MULTIMEDIA and hasattr(self, "video_player"):
                self.video_player.show()
                self.video_player.load_video(path)
        elif ext in {".txt", ".log", ".json", ".xml", ".py", ".md", ".csv", ".plist", ".html", ".css", ".js"}:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(10000)
                    self.text_edit.setText(content)
                    self.text_edit.show()
                except Exception:
                    pass
        else:
            # ⚡ Instant Pixmap Retrieval with Caching & Prefetching!
            pix = self._get_cached_pixmap(path)
            if pix and not pix.isNull():
                self.current_pixmap = pix
                self.zoom_factor = 1.0
                self.fit_mode = "fit"
                self._is_dragging = False
                self._update_image_display()
                self.scroll_area.show()
                QTimer.singleShot(0, self._center_image_scrollbars)

            # Trigger background prefetching for adjacent images
            self._prefetch_adjacent_images()

    def _center_image_scrollbars(self):
        """Reset scrollbars so every new image opens 100% centered in the preview window."""
        if hasattr(self, "scroll_area") and self.scroll_area:
            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()
            h_bar.setValue((h_bar.minimum() + h_bar.maximum()) // 2)
            v_bar.setValue((v_bar.minimum() + v_bar.maximum()) // 2)

    def _on_location_ready(self, path, location_text):
        if self.file_list and (0 <= self.current_index < len(self.file_list)):
            curr_item = self.file_list[self.current_index]
            curr_path = curr_item if isinstance(curr_item, str) else getattr(curr_item, "path", str(curr_item))
            if curr_path == path:
                self.location_lbl.setText(location_text)

    def _get_cached_pixmap(self, path):
        if not hasattr(self, "_pix_cache"):
            self._pix_cache = {}

        if path in self._pix_cache:
            return self._pix_cache[path]

        pix = None
        if isinstance(path, str) and os.path.exists(path):
            ext = Path(path).suffix.lower()
            qimg = QImage()
            if ext in {".heic", ".heif"} and platform.system() == "Darwin":
                tmp = os.path.join(tempfile.gettempdir(), f"_heic_ql_{os.getpid()}_{abs(hash(path))}.png")
                ret = os.system(f'sips -s format png "{path}" --out "{tmp}" >/dev/null 2>&1')
                if ret == 0 and os.path.exists(tmp):
                    reader = QImageReader(tmp)
                    reader.setAutoTransform(True)
                    qimg = reader.read()
                    try: os.unlink(tmp)
                    except Exception: pass
            else:
                reader = QImageReader(path)
                reader.setAutoTransform(True)
                qimg = reader.read()

            if not qimg.isNull():
                pix = QPixmap.fromImage(qimg)
                if len(self._pix_cache) > 30:
                    self._pix_cache.clear()
                self._pix_cache[path] = pix

        return pix

    def _prefetch_adjacent_images(self):
        for offset in (1, -1):
            idx = self.current_index + offset
            if 0 <= idx < len(self.file_list):
                item = self.file_list[idx]
                p = item if isinstance(item, str) else getattr(item, "path", str(item))
                if p and p not in self._pix_cache:
                    QTimer.singleShot(10, lambda path_to_load=p: self._get_cached_pixmap(path_to_load))

    def _update_image_display(self):
        if not self.current_pixmap:
            return
            
        w = self.current_pixmap.width()
        h = self.current_pixmap.height()
        
        area_w = self.scroll_area.viewport().width() - 20
        area_h = self.scroll_area.viewport().height() - 20
        if area_w <= 100 or area_h <= 100:
            area_w, area_h = 800, 500
            
        if self.fit_mode == "fit":
            scaled_pix = self.current_pixmap.scaled(
                area_w, area_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        elif self.fit_mode == "actual":
            scaled_pix = self.current_pixmap
        else: # custom zoom
            target_w = int(w * self.zoom_factor)
            target_h = int(h * self.zoom_factor)
            scaled_pix = self.current_pixmap.scaled(
                target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            
        self.img_lbl.setPixmap(scaled_pix)
        QTimer.singleShot(10, self._update_cursor_mode)

    def _get_fit_scale_ratio(self):
        if not self.current_pixmap or self.current_pixmap.isNull():
            return 1.0
        w = self.current_pixmap.width()
        h = self.current_pixmap.height()
        if w <= 0 or h <= 0:
            return 1.0
        area_w = self.scroll_area.viewport().width() - 20
        area_h = self.scroll_area.viewport().height() - 20
        if area_w <= 100 or area_h <= 100:
            area_w, area_h = 800, 500
        return min(area_w / float(w), area_h / float(h))

    def _zoom_in(self):
        if self.fit_mode == "fit":
            self.fit_mode = "custom"
            self.zoom_factor = self._get_fit_scale_ratio() * 1.15
        elif self.fit_mode == "actual":
            self.fit_mode = "custom"
            self.zoom_factor = 1.15
        else:
            self.zoom_factor *= 1.15
        self._update_image_display()

    def _zoom_out(self):
        if self.fit_mode == "fit":
            self.fit_mode = "custom"
            self.zoom_factor = self._get_fit_scale_ratio() / 1.15
        elif self.fit_mode == "actual":
            self.fit_mode = "custom"
            self.zoom_factor = 1.0 / 1.15
        else:
            self.zoom_factor /= 1.15
        if self.zoom_factor < 0.05:
            self.zoom_factor = 0.05
        self._update_image_display()

    def _fit_to_window(self):
        self.fit_mode = "fit"
        self.zoom_factor = 1.0
        self._is_dragging = False
        self._update_image_display()
        QTimer.singleShot(0, self._center_image_scrollbars)

    def _actual_size(self):
        self.fit_mode = "actual"
        self.zoom_factor = 1.0
        self._update_image_display()

    def _on_slider_seek(self, pos):
        if self.player.duration() > 0:
            target_ms = int((pos / 1000.0) * self.player.duration())
            self.player.setPosition(target_ms)

    def _on_pos_changed(self, pos):
        if not self.timeline_slider.isSliderDown() and self.player.duration() > 0:
            val = int((pos / float(self.player.duration())) * 1000)
            self.timeline_slider.setValue(val)
        self._update_time(pos, self.player.duration())

    def _on_dur_changed(self, dur):
        self._update_time(self.player.position(), dur)

    def _update_time(self, pos, dur):
        def fmt(ms):
            s = int(ms / 1000)
            m = s // 60
            s = s % 60
            return f"{m:02d}:{s:02d}"
        self.time_lbl.setText(f"{fmt(pos)} / {fmt(dur)}")

    def _toggle_fullscreen(self):
        if self.isMaximized() or self.isFullScreen():
            self.showNormal()
            if hasattr(self, "maximize_btn"):
                self.maximize_btn.setText("⛶ Fullscreen")
        else:
            self.showMaximized()
            if hasattr(self, "maximize_btn"):
                self.maximize_btn.setText("🗗 Restore")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "fit_mode") and self.fit_mode == "fit":
            QTimer.singleShot(10, self._update_image_display)


# ── Dynamic Placeholders ──────────────────────────────────────────────────────
def make_placeholder_pixmap(ext: str, size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(QColor("#0d0d0d"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    font = QFont(".AppleSystemUIFont", max(8, int(size * 0.11)), QFont.Bold)
    painter.setFont(font)
    
    if ext in VIDEO_EXTS:
        painter.setPen(QPen(QColor(ACCENT2)))
    else:
        painter.setPen(QPen(QColor(SUBTEXT)))
        
    rect = pix.rect()
    text = ext.upper().replace(".", "")
    painter.drawText(rect, Qt.AlignCenter, text)
    
    painter.setPen(QPen(QColor(BORDER), 1))
    painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 4, 4)
    painter.end()
    return pix

def make_folder_pixmap(size: int) -> QPixmap:
    # Try loading folder2.png with transparent background
    script_dir = os.path.dirname(os.path.abspath(__file__))
    folder2_png = os.path.join(script_dir, "folder2.png")
    folder_png = os.path.join(script_dir, "folder.png")
    folder_jpg = os.path.join(script_dir, "folder.jpg")
    
    icon_path = None
    if os.path.exists(folder2_png):
        icon_path = folder2_png
    elif os.path.exists(folder_png):
        icon_path = folder_png
    elif os.path.exists(folder_jpg):
        icon_path = folder_jpg

    if icon_path and os.path.exists(icon_path):
        pix_loaded = QPixmap(icon_path)
        if not pix_loaded.isNull():
            scaled = pix_loaded.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            out_pix = QPixmap(size, size)
            out_pix.fill(QColor(0, 0, 0, 0)) # transparent background
            painter = QPainter(out_pix)
            dx = (size - scaled.width()) // 2
            dy = (size - scaled.height()) // 2
            painter.drawPixmap(dx, dy, scaled)
            painter.end()
            return out_pix

    pix = QPixmap(size, size)
    pix.fill(QColor("#0d0d0d"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    
    w = int(size * 0.72)
    h = int(size * 0.54)
    x = int((size - w) / 2)
    y = int((size - h) / 2) + 4
    
    # Back cover gradient (darker blue)
    back_grad = QLinearGradient(x, y, x, y + h)
    back_grad.setColorAt(0.0, QColor("#005ecb"))
    back_grad.setColorAt(1.0, QColor("#003b80"))
    
    painter.setPen(QPen(QColor("#007aff"), 1))
    painter.setBrush(QBrush(back_grad))
    tab_w = int(w * 0.4)
    tab_h = int(h * 0.2)
    painter.drawRoundedRect(QRect(x, y - tab_h + 2, tab_w, tab_h + 5), 4, 4)
    painter.drawRoundedRect(QRect(x, y, w, h), 6, 6)
    
    # Lined paper sheet detail
    paper_grad = QLinearGradient(x + 10, y - 6, x + 10, y + 10)
    paper_grad.setColorAt(0.0, QColor("#ffffff"))
    paper_grad.setColorAt(1.0, QColor("#e0e0e0"))
    painter.setPen(QPen(QColor("#cccccc"), 1))
    painter.setBrush(QBrush(paper_grad))
    painter.drawRoundedRect(QRect(x + 12, y - 6, w - 24, h - 10), 2, 2)
    
    painter.setPen(QPen(QColor("#bbbbbb"), 1))
    painter.drawLine(x + 18, y - 1, x + w - 18, y - 1)
    painter.drawLine(x + 18, y + 4, x + w - 24, y + 4)
    
    # Front cover gradient (brighter blue)
    front_grad = QLinearGradient(x, y + 8, x, y + h)
    front_grad.setColorAt(0.0, QColor("#3ea8ff"))
    front_grad.setColorAt(1.0, QColor("#007aff"))
    
    painter.setPen(QPen(QColor("#54b4ff"), 1.5))
    painter.setBrush(QBrush(front_grad))
    painter.drawRoundedRect(QRect(x, y + 8, w, h - 8), 6, 6)
    
    painter.setPen(QPen(QColor("rgba(255,255,255,0.2)"), 1))
    painter.drawLine(x + 4, y + 12, x + w - 4, y + 12)
    
    painter.end()
    return pix

# ── Asynchronous Local Image Loader ───────────────────────────────────────────
class LocalThumbSignals(QObject):
    done = Signal(str, QImage, str)

class LocalThumbLoader(QRunnable):
    def __init__(self, path: str, size: int, signals: LocalThumbSignals):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = signals
        self.setAutoDelete(True)

    def run(self):
        try:
            ext = Path(self.path).suffix.lower()
            qimg = QImage()
            if ext in {".heic", ".heif"} and platform.system() == "Darwin":
                tmp = os.path.join(tempfile.gettempdir(), f"_heic_thumb_{os.getpid()}_{abs(hash(self.path))}.png")
                ret = os.system(f'sips -z {self.size*2} {self.size*2} -s format png "{self.path}" --out "{tmp}" >/dev/null 2>&1')
                if ret == 0 and os.path.exists(tmp):
                    qimg.load(tmp)
                    try:
                        os.unlink(tmp)
                    except Exception:
                        pass
            elif ext in VIDEO_EXTS:
                tmp = os.path.join(tempfile.gettempdir(), f"_qt_thumb_{os.getpid()}_{abs(hash(self.path))}.png")
                ret = os.system(f'ffmpeg -y -i "{self.path}" -vframes 1 -vf "scale={self.size*2}:-1" -q:v 2 "{tmp}" >/dev/null 2>&1')
                if ret == 0 and os.path.exists(tmp):
                    qimg.load(tmp)
                    try:
                        os.unlink(tmp)
                    except Exception:
                        pass
            else:
                # Fast sub-sampled decode using QImageReader (10x - 20x faster!)
                reader = QImageReader(self.path)
                reader.setAutoTransform(True)
                orig_sz = reader.size()
                if orig_sz.isValid() and orig_sz.width() > 0:
                    target_s = self.size * 2
                    scaled_sz = orig_sz.scaled(target_s, target_s, Qt.KeepAspectRatio)
                    reader.setScaledSize(scaled_sz)
                    qimg = reader.read()
                else:
                    qimg.load(self.path)
            
            if qimg.isNull():
                self.signals.done.emit(self.path, QImage(), ext)
            else:
                if qimg.width() > self.size * 2 or qimg.height() > self.size * 2:
                    qimg = qimg.scaled(self.size * 2, self.size * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.signals.done.emit(self.path, qimg, "")
        except Exception:
            try:
                ext = Path(self.path).suffix.lower()
                self.signals.done.emit(self.path, QImage(), ext)
            except Exception:
                pass

_local_thumb_pool = QThreadPool()
_local_thumb_pool.setMaxThreadCount(16)
_local_thumb_cache = {}
_active_local_signals = set()

def get_local_thumb_async(path: str, size: int, callback):
    cache_key = f"{path}_{size}"
    if cache_key in _local_thumb_cache:
        callback(path, _local_thumb_cache[cache_key])
        return
    sig = LocalThumbSignals()
    _active_local_signals.add(sig)
    
    def _cb(p, qimg, ext):
        try:
            if not qimg.isNull():
                px = QPixmap.fromImage(qimg)
            else:
                px = make_placeholder_pixmap(ext, size)
            _local_thumb_cache[cache_key] = px
            
            if shiboken and hasattr(callback, '__self__'):
                obj = callback.__self__
                if not shiboken.isValid(obj):
                    return
                if not getattr(obj, "_is_active", True):
                    return
            callback(p, px)
        except Exception:
            pass
        finally:
            _active_local_signals.discard(sig)
    sig.done.connect(_cb, Qt.QueuedConnection)
    loader = LocalThumbLoader(path, size, sig)
    _local_thumb_pool.start(loader)

# Helper functions for GetInfoDialog & Folder Size Calculation
class FolderSizeSignals(QObject):
    done = Signal(str, object)

class FolderSizeWorker(QRunnable):
    def __init__(self, folder_path, signals):
        super().__init__()
        self.folder_path = folder_path
        self.signals = signals

    def run(self):
        total_bytes = 0
        try:
            for root, dirs, files in os.walk(self.folder_path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        if os.path.exists(fp):
                            total_bytes += os.path.getsize(fp)
                    except Exception:
                        pass
        except Exception:
            pass
        self.signals.done.emit(self.folder_path, total_bytes)

def get_folder_size_and_count(folder_path):
    total = 0
    file_count = 0
    folder_count = 0
    try:
        for root, dirs, files in os.walk(folder_path):
            folder_count += len(dirs)
            for f in files:
                fp = os.path.join(root, f)
                try:
                    if os.path.exists(fp):
                        total += os.path.getsize(fp)
                        file_count += 1
                except Exception:
                    pass
    except Exception:
        pass
    return total, file_count, folder_count

def get_folder_size(folder_path):
    sz, _, _ = get_folder_size_and_count(folder_path)
    return sz

def get_video_info(path):
    try:
        import subprocess
        import json
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_name", "-of", "json", path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.0)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            width = data['streams'][0]['width']
            height = data['streams'][0]['height']
            duration = float(data['format']['duration'])
            codec = data['streams'][0]['codec_name']
            return width, height, duration, codec
    except Exception:
        pass
    return None

# ── Get Info Dialog ───────────────────────────────────────────────────────────
from PySide6.QtWidgets import QDialog
from PySide6.QtGui import QImageReader

class GetInfoDialog(QDialog):
    def __init__(self, item, is_iphone=False, parent=None):
        super().__init__(parent)
        self.item = item
        self.is_iphone = is_iphone
        self._is_active = True
        
        self.setWindowTitle("Get Info")
        self.setFixedSize(380, 520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {PANEL_BG};
                color: {TEXT};
                border: 1px solid {BORDER};
            }}
            QLabel {{
                color: {TEXT};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }}
            QPushButton {{
                background-color: {BTN_BG};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {BTN_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {BTN_PRESSED};
            }}
        """)
        self._build_ui()
        self._load_metadata()

    def closeEvent(self, event):
        self._is_active = False
        super().closeEvent(event)

    def _build_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(16, 16, 16, 16)
        main_lay.setSpacing(12)

        # Header Area: Icon, Name, Kind
        hdr_lay = QHBoxLayout()
        hdr_lay.setSpacing(12)
        
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(64, 64)
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet(f"background: #0d0d0d; border-radius: 8px; border: 1px solid {BORDER};")
        
        hdr_lay.addWidget(self.icon_lbl)

        hdr_info = QVBoxLayout()
        hdr_info.setSpacing(2)
        self.name_lbl = QLabel()
        self.name_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT};")
        self.name_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.name_lbl.setWordWrap(True)
        
        self.kind_sub_lbl = QLabel()
        self.kind_sub_lbl.setStyleSheet(f"font-size: 11px; color: {SUBTEXT};")
        
        hdr_info.addWidget(self.name_lbl)
        hdr_info.addWidget(self.kind_sub_lbl)
        hdr_info.addStretch()
        hdr_lay.addLayout(hdr_info, 1)
        
        main_lay.addLayout(hdr_lay)

        # General Section
        main_lay.addWidget(self._create_section_hdr("General"))
        
        self.grid = QGridLayout()
        self.grid.setSpacing(6)
        self.grid.setColumnMinimumWidth(0, 80)
        main_lay.addLayout(self.grid)

        # More Info Section (Placeholder)
        self.more_info_hdr = None
        self.more_info_grid = None
        
        # Permissions Section (Placeholder)
        self.perm_hdr = None
        self.perm_grid = None

        main_lay.addStretch()

        # Footer Actions
        footer_lay = QHBoxLayout()
        footer_lay.setSpacing(8)
        
        if not self.is_iphone:
            show_btn = QPushButton("Show in Finder")
            show_btn.clicked.connect(self._show_in_finder)
            footer_lay.addWidget(show_btn)
            
            copy_btn = QPushButton("Copy Path")
            copy_btn.clicked.connect(self._copy_path)
            footer_lay.addWidget(copy_btn)
            
        footer_lay.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        footer_lay.addWidget(close_btn)
        
        main_lay.addLayout(footer_lay)

    def _create_section_hdr(self, title):
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 8, 0, 4)
        lay.setSpacing(4)
        
        lbl = QLabel(title)
        lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {ACCENT}; text-transform: uppercase; letter-spacing: 0.5px;")
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet(f"background-color: {BORDER}; max-height: 1px; border: none;")
        
        lay.addWidget(lbl)
        lay.addWidget(line)
        return widget

    def _create_value_lbl(self, val, selectable=False):
        lbl = QLabel(str(val))
        lbl.setStyleSheet(f"font-size: 11px; color: {TEXT};")
        if selectable:
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setWordWrap(True)
        return lbl

    def _add_more_info_section(self):
        if self.more_info_hdr is not None:
            return
        layout = self.layout()
        idx = layout.count() - 2
        
        self.more_info_hdr = self._create_section_hdr("More Info")
        layout.insertWidget(idx, self.more_info_hdr)
        
        self.more_info_grid = QGridLayout()
        self.more_info_grid.setSpacing(6)
        self.more_info_grid.setColumnMinimumWidth(0, 80)
        layout.insertLayout(idx + 1, self.more_info_grid)

    def _add_permissions_section(self, path):
        layout = self.layout()
        idx = layout.count() - 2
        
        self.perm_hdr = self._create_section_hdr("Sharing & Permissions")
        layout.insertWidget(idx, self.perm_hdr)
        
        self.perm_grid = QGridLayout()
        self.perm_grid.setSpacing(6)
        self.perm_grid.setColumnMinimumWidth(0, 80)
        
        import stat
        try:
            st = os.stat(path)
            mode = st.st_mode
            owner_r = "Read" if mode & stat.S_IRUSR else "No Read"
            owner_w = "Write" if mode & stat.S_IWUSR else "No Write"
            owner_perm = f"{owner_r} & {owner_w}"
            
            group_r = "Read" if mode & stat.S_IRGRP else "No Read"
            group_w = "Write" if mode & stat.S_IWGRP else "No Write"
            group_perm = f"{group_r} & {group_w}"
            
            other_r = "Read" if mode & stat.S_IROTH else "No Read"
            other_w = "Write" if mode & stat.S_IWOTH else "No Write"
            other_perm = f"{other_r} & {other_w}"
        except Exception:
            owner_perm = "Read & Write"
            group_perm = "Read Only"
            other_perm = "Read Only"
            
        self.perm_grid.addWidget(QLabel("Owner:"), 0, 0)
        self.perm_grid.addWidget(self._create_value_lbl(owner_perm), 0, 1)
        self.perm_grid.addWidget(QLabel("Group:"), 1, 0)
        self.perm_grid.addWidget(self._create_value_lbl(group_perm), 1, 1)
        self.perm_grid.addWidget(QLabel("Everyone:"), 2, 0)
        self.perm_grid.addWidget(self._create_value_lbl(other_perm), 2, 1)
        
        layout.insertLayout(idx + 1, self.perm_grid)

    def _load_metadata(self):
        if self.is_iphone:
            name = self.item.name()
            self.name_lbl.setText(name)
            
            ext = os.path.splitext(name)[1].lower()
            kind_str = "iPhone Media File"
            if ext in VIDEO_EXTS:
                kind_str = "MOV Video" if ext == ".mov" else f"{ext[1:].upper()} Video"
            elif ext in EXTS:
                kind_str = f"{ext[1:].upper()} Image"
            self.kind_sub_lbl.setText(kind_str)
            
            self.icon_lbl.setPixmap(make_placeholder_pixmap(ext, 64))
            
            self.grid.addWidget(QLabel("Kind:"), 0, 0)
            self.grid.addWidget(self._create_value_lbl(kind_str), 0, 1)
            
            sz = self.item.fileSize()
            sz_str = f"{format_size(sz)} ({sz:,} bytes)"
            self.grid.addWidget(QLabel("Size:"), 1, 0)
            self.grid.addWidget(self._create_value_lbl(sz_str), 1, 1)
            
            self.grid.addWidget(QLabel("Where:"), 2, 0)
            self.grid.addWidget(self._create_value_lbl("iPhone Camera Roll"), 2, 1)
            
            created_str = ""
            if hasattr(self.item, "creationDate") and self.item.creationDate():
                created_str = str(self.item.creationDate())[:19]
            self.grid.addWidget(QLabel("Created:"), 3, 0)
            self.grid.addWidget(self._create_value_lbl(created_str or "Unknown"), 3, 1)
            
            modified_str = ""
            if hasattr(self.item, "modificationDate") and self.item.modificationDate():
                modified_str = str(self.item.modificationDate())[:19]
            self.grid.addWidget(QLabel("Modified:"), 4, 0)
            self.grid.addWidget(self._create_value_lbl(modified_str or "Unknown"), 4, 1)
            
            w = 0
            h = 0
            if hasattr(self.item, "pixelWidth"):
                try:
                    w = self.item.pixelWidth()
                    h = self.item.pixelHeight()
                except Exception:
                    try:
                        w = self.item.pixelWidth
                        h = self.item.pixelHeight
                    except Exception:
                        pass
            elif isinstance(self.item, SimulatedCameraFile):
                w, h = 4032, 3024
                
            if w and h:
                self._add_more_info_section()
                self.more_info_grid.addWidget(QLabel("Dimensions:"), 0, 0)
                self.more_info_grid.addWidget(self._create_value_lbl(f"{w} × {h}"), 0, 1)
                
            if hasattr(self.item, "duration") and self.item.duration():
                try:
                    d = float(self.item.duration())
                    if d > 0:
                        self._add_more_info_section()
                        dur_str = f"{int(d // 60):02d}:{int(d % 60):02d}"
                        self.more_info_grid.addWidget(QLabel("Duration:"), 1, 0)
                        self.more_info_grid.addWidget(self._create_value_lbl(dur_str), 1, 1)
                except Exception:
                    pass
                
            get_iphone_thumb_async(self.item, 64, self._on_thumb_loaded)
        else:
            path = self.item
            name = os.path.basename(path)
            self.name_lbl.setText(name)
            
            is_dir = os.path.isdir(path)
            if is_dir:
                kind_str = "Folder"
                self.icon_lbl.setPixmap(make_folder_pixmap(64))
            else:
                ext = os.path.splitext(name)[1].lower()
                kind_str = f"{ext[1:].upper()} File"
                if ext in VIDEO_EXTS:
                    kind_str = f"{ext[1:].upper()} Video"
                elif ext in EXTS:
                    kind_str = f"{ext[1:].upper()} Image"
                self.icon_lbl.setPixmap(make_placeholder_pixmap(ext, 64))
            self.kind_sub_lbl.setText(kind_str)
            
            self.grid.addWidget(QLabel("Kind:"), 0, 0)
            self.grid.addWidget(self._create_value_lbl(kind_str), 0, 1)
            
            if is_dir:
                sz, file_count, folder_count = get_folder_size_and_count(path)
                if folder_count > 0:
                    sz_str = f"{format_size(sz)} ({sz:,} bytes) for {file_count} files, {folder_count} folders"
                else:
                    sz_str = f"{format_size(sz)} ({sz:,} bytes) for {file_count} items"
            else:
                sz = os.path.getsize(path)
                sz_str = f"{format_size(sz)} ({sz:,} bytes)"
            self.grid.addWidget(QLabel("Size:"), 1, 0)
            self.grid.addWidget(self._create_value_lbl(sz_str), 1, 1)
            
            self.grid.addWidget(QLabel("Where:"), 2, 0)
            self.grid.addWidget(self._create_value_lbl(os.path.dirname(path), selectable=True), 2, 1)
            
            try:
                stat_res = os.stat(path)
                created_val = getattr(stat_res, 'st_birthtime', stat_res.st_ctime)
                created_str = datetime.fromtimestamp(created_val).strftime('%Y-%m-%d %H:%M:%S')
                modified_str = datetime.fromtimestamp(stat_res.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                created_str = "Unknown"
                modified_str = "Unknown"
            
            self.grid.addWidget(QLabel("Created:"), 3, 0)
            self.grid.addWidget(self._create_value_lbl(created_str), 3, 1)
            
            self.grid.addWidget(QLabel("Modified:"), 4, 0)
            self.grid.addWidget(self._create_value_lbl(modified_str), 4, 1)
            
            if not is_dir:
                ext = os.path.splitext(name)[1].lower()
                if ext in EXTS and ext not in VIDEO_EXTS:
                    reader = QImageReader(path)
                    sz_size = reader.size()
                    if sz_size.isValid():
                        self._add_more_info_section()
                        self.more_info_grid.addWidget(QLabel("Dimensions:"), 0, 0)
                        self.more_info_grid.addWidget(self._create_value_lbl(f"{sz_size.width()} × {sz_size.height()}"), 0, 1)
                    
                    gps_coords = extract_image_exif_gps(path)
                    if gps_coords:
                        loc_name = get_location_name_from_coords(gps_coords[0], gps_coords[1])
                        self._add_more_info_section()
                        row_idx = self.more_info_grid.rowCount()
                        self.more_info_grid.addWidget(QLabel("Location:"), row_idx, 0)
                        self.more_info_grid.addWidget(self._create_value_lbl(f"{loc_name} ({gps_coords[0]:.4f}°, {gps_coords[1]:.4f}°)", selectable=True), row_idx, 1)
                elif ext in VIDEO_EXTS:
                    vinfo = get_video_info(path)
                    if vinfo:
                        w, h, duration, codec = vinfo
                        self._add_more_info_section()
                        self.more_info_grid.addWidget(QLabel("Dimensions:"), 0, 0)
                        self.more_info_grid.addWidget(self._create_value_lbl(f"{w} × {h}"), 0, 1)
                        
                        dur_str = f"{int(duration // 60):02d}:{int(duration % 60):02d}"
                        self.more_info_grid.addWidget(QLabel("Duration:"), 1, 0)
                        self.more_info_grid.addWidget(self._create_value_lbl(dur_str), 1, 1)
                        
                        if codec:
                            self.more_info_grid.addWidget(QLabel("Codecs:"), 2, 0)
                            self.more_info_grid.addWidget(self._create_value_lbl(codec.upper()), 2, 1)
                            
            self._add_permissions_section(path)
            
            if not is_dir:
                get_local_thumb_async(path, 64, self._on_thumb_loaded)

    def _on_thumb_loaded(self, path_or_name, px):
        if not getattr(self, "_is_active", True):
            return
        if shiboken and not shiboken.isValid(self):
            return
        try:
            if not px.isNull():
                self.icon_lbl.setPixmap(px.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            pass

    def _show_in_finder(self):
        if not self.is_iphone and hasattr(self, "item") and self.item:
            if platform.system() == "Darwin":
                if HAS_PYOBJC:
                    try:
                        from AppKit import NSWorkspace
                        ws = NSWorkspace.sharedWorkspace()
                        if ws and ws.selectFile_inFileViewerRootedAtPath_(self.item, None):
                            return
                    except Exception as e:
                        print(f"NSWorkspace reveal exception: {e}")
                try:
                    subprocess.Popen(["open", "-R", self.item], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    print(f"open -R exception: {e}")
                    try:
                        subprocess.Popen(["open", os.path.dirname(self.item)])
                    except Exception:
                        pass

    def _copy_path(self):
        if not self.is_iphone:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.item)

# ── Local File Card ───────────────────────────────────────────────────────────
class LocalCard(QFrame):
    clicked = Signal(object)
    double_clicked = Signal(object)

    def __init__(self, path: str, is_folder: bool = False, parent=None):
        super().__init__(parent)
        self.path = path
        self.is_folder = is_folder
        self.selected = False
        self.drag_start_position = QPoint()
        self.setFixedSize(THUMB_SIZE + 16, THUMB_SIZE + 42)
        self.setCursor(Qt.PointingHandCursor)
        self._is_active = True
        self._setup()
        if self.is_folder:
            self.setAcceptDrops(True)

    def _setup(self):
        self._update_style()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 4)
        lay.setSpacing(3)

        self.img_lbl = QLabel(alignment=Qt.AlignCenter)
        self.img_lbl.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.img_lbl.setStyleSheet(f"background:{CARD_BG}; border-radius:6px;")
        self.img_lbl.setScaledContents(True)
        lay.addWidget(self.img_lbl)

        bot = QHBoxLayout()
        bot.setContentsMargins(0,0,0,0)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        
        self.name_lbl = QLabel()
        self.name_lbl.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:600;")
        self.name_lbl.setMaximumWidth(THUMB_SIZE - 32)
        
        self.menu_btn = QPushButton("⋮")
        self.menu_btn.setFixedSize(16, 16)
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.clicked.connect(self._show_context_menu)
        self.menu_btn.setStyleSheet(f"""
            QPushButton {{
                color: {SUBTEXT};
                background: transparent;
                border: none;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                color: white;
                background: rgba(255,255,255,0.1);
                border-radius: 3px;
            }}
        """)
        
        bot.addWidget(self.dot)
        bot.addWidget(self.name_lbl, 1)
        bot.addWidget(self.menu_btn)
        lay.addLayout(bot)

        if self.is_folder:
            self.dot.setStyleSheet("background:#888888; border-radius:4px;")
            self.img_lbl.setPixmap(make_folder_pixmap(THUMB_SIZE))
            if self.path == "..":
                self.name_lbl.setText(".. (Go Up)")
                self.menu_btn.hide()
            else:
                nm = Path(self.path).name
                self.name_lbl.setText(nm if len(nm)<=15 else nm[:12]+"…")
        else:
            self.dot.setStyleSheet(f"background:{DOT_DONE}; border-radius:4px;")
            nm = Path(self.path).name
            self.name_lbl.setText(nm if len(nm)<=15 else nm[:12]+"…")
            get_local_thumb_async(self.path, THUMB_SIZE, self._on_thumb)

    def _on_thumb(self, path, px):
        if not getattr(self, "_is_active", True):
            return
        if shiboken and not shiboken.isValid(self):
            return
        try:
            if path == self.path:
                if shiboken and shiboken.isValid(self.img_lbl):
                    self.img_lbl.setPixmap(px)
        except RuntimeError:
            pass

    def _update_style(self):
        border_color = ACCENT if self.selected else BORDER
        hover_border = ACCENT if self.selected else SCROLLBAR_HANDLE
        self.setStyleSheet(f"""
            LocalCard {{
                background: {PANEL_BG};
                border: 1.5px solid {border_color};
                border-radius: 10px;
            }}
            LocalCard:hover {{
                background: {HOVER_BG};
                border-color: {hover_border};
            }}
        """)

    def set_selected(self, v: bool):
        self.selected = v
        self._update_style()

    def mousePressEvent(self, e):
        p = self.parentWidget()
        while p:
            if hasattr(p, "focused"):
                p.focused.emit()
                break
            p = p.parentWidget()

        if e.button() == Qt.LeftButton:
            self.drag_start_position = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            curr_pos = e.position().toPoint()
            if (curr_pos - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
                self.clicked.emit(self)
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.double_clicked.emit(self)
        super().mouseDoubleClickEvent(e)

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(e)
            return
        if (e.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(e)
            return
        if self.path == "..":
            return

        p = self.parentWidget()
        selected_paths = []
        while p:
            if hasattr(p, "get_selected"):
                selected_paths = p.get_selected()
                break
            p = p.parentWidget()
            
        if self.path not in selected_paths:
            selected_paths = [self.path]
            
        selected_paths = [path for path in selected_paths if path != ".."]
        if not selected_paths:
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        
        paths_data = "\n".join(selected_paths).encode('utf-8')
        mime_data.setData("application/x-local-files", paths_data)
        
        urls = [QUrl.fromLocalFile(path) for path in selected_paths]
        mime_data.setUrls(urls)
        
        drag.setMimeData(mime_data)

        pix = self.img_lbl.pixmap()
        if pix and not pix.isNull():
            drag.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            drag.setHotSpot(QPoint(32, 32))

        drag.exec(Qt.CopyAction)

    def dragEnterEvent(self, e):
        if self.is_folder and (e.mimeData().hasFormat("application/x-local-files") or e.mimeData().hasFormat("application/x-iphone-files")):
            e.acceptProposedAction()
            self.setStyleSheet(f"""
                LocalCard {{
                    background: rgba(10, 132, 255, 0.15);
                    border: 2px dashed {ACCENT};
                    border-radius: 10px;
                }}
            """)

    def dragLeaveEvent(self, e):
        self._update_style()

    def dropEvent(self, e):
        self._update_style()
        target_dir = self.path
        if self.path == "..":
            p = self.parentWidget()
            while p:
                if hasattr(p, "current_path"):
                    target_dir = str(Path(p.current_path).parent)
                    break
                p = p.parentWidget()
                
        p_panel = self.parentWidget()
        while p_panel:
            if hasattr(p_panel, "copy_local_items"):
                break
            p_panel = p_panel.parentWidget()
            
        if not p_panel: return

        dest_name = os.path.basename(target_dir) or target_dir
        if e.mimeData().hasFormat("application/x-local-files"):
            paths_str = e.mimeData().data("application/x-local-files").data().decode('utf-8')
            paths = [p for p in paths_str.split("\n") if p]
            if paths:
                reply = ask_user_confirmation(
                    self,
                    "Confirm Drag & Drop Copy",
                    f"Are you sure you want to copy {len(paths)} item(s) into '{dest_name}'?"
                )
                if reply == QMessageBox.Yes:
                    p_panel.copy_local_items(paths, target_dir)
                    e.acceptProposedAction()
            
        elif e.mimeData().hasFormat("application/x-iphone-files"):
            mw = self.window()
            if mw and hasattr(mw, "_start_download_queue"):
                files = mw.iphone_panel.get_selected()
                if files:
                    reply = ask_user_confirmation(
                        self,
                        "Confirm Drag & Drop Copy",
                        f"Are you sure you want to copy {len(files)} iPhone file(s) into '{dest_name}'?"
                    )
                    if reply == QMessageBox.Yes:
                        mw._start_download_queue(files, custom_dest=target_dir)
                        e.acceptProposedAction()

    def contextMenuEvent(self, e):
        if self.path != "..":
            self._show_context_menu()
            e.accept()

    def _show_context_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {HEADER};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {ACCENT};
                color: white;
            }}
        """)
        
        info_action = QAction("Get Info", self)
        info_action.triggered.connect(self._show_info)
        
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self._copy_item)

        paste_action = QAction("Paste", self)
        paste_action.triggered.connect(self._paste_item)
        
        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(self._rename_item)
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._delete_item)
        
        menu.addAction(info_action)
        menu.addSeparator()
        menu.addAction(copy_action)
        mw = self.window()
        has_clip = bool(getattr(mw, "clipboard_files", None) or QApplication.clipboard().mimeData().hasUrls())
        paste_action.setEnabled(has_clip)
        menu.addAction(paste_action)
        menu.addSeparator()
        menu.addAction(rename_action)
        menu.addAction(delete_action)
        menu.exec(QCursor.pos())

    def _copy_item(self):
        parent_panel = getattr(self, "parent_panel", None)
        if parent_panel and hasattr(parent_panel, "_copy_selected_files"):
            parent_panel._copy_selected_files()

    def _paste_item(self):
        parent_panel = getattr(self, "parent_panel", None)
        if parent_panel and hasattr(parent_panel, "_paste_files_here"):
            parent_panel._paste_files_here()

    def _show_info(self):
        dialog = GetInfoDialog(self.path, is_iphone=False, parent=self.window())
        dialog.exec()

    def _rename_item(self):
        p = self.parentWidget()
        while p:
            if hasattr(p, "_rename_path"):
                p._rename_path(self.path)
                break
            p = p.parentWidget()

    def _delete_item(self):
        p = self.parentWidget()
        while p:
            if hasattr(p, "_delete_path"):
                p._delete_path(self.path)
                break
            p = p.parentWidget()

# ── Table Cell Preview Widget (Details Mode) ─────────────────────────────────
class TablePreviewWidget(QLabel):
    def __init__(self, path_or_file, is_folder=False, is_iphone=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"background: {CARD_BG}; border-radius: 3px;")
        self._is_active = True
        
        if is_folder:
            self.setPixmap(make_folder_pixmap(16))
        else:
            if is_iphone:
                get_iphone_thumb_async(path_or_file, 16, self._on_thumb)
            else:
                get_local_thumb_async(path_or_file, 16, self._on_thumb)
                
    def _on_thumb(self, name, px):
        if not getattr(self, "_is_active", True):
            return
        if shiboken and not shiboken.isValid(self):
            return
        try:
            self.setPixmap(px.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except RuntimeError:
            pass

# ── Asynchronous iPhone Image Loader ──────────────────────────────────────────
class IPhoneThumbSignals(QObject):
    done = Signal(str, QImage, str)

class IPhoneThumbLoader(QRunnable):
    def __init__(self, file_object, size: int, signals: IPhoneThumbSignals):
        super().__init__()
        self.file_object = file_object
        self.size = size
        self.signals = signals
        self.setAutoDelete(True)

    def run(self):
        try:
            if isinstance(self.file_object, SimulatedCameraFile):
                ext = Path(self.file_object.name()).suffix.lower()
                self.signals.done.emit(self.file_object.name(), QImage(), ext)
                return

            with objc.autorelease_pool():
                data = self.file_object.thumbnailData()
                qimg = QImage()
                if data:
                    byte_data = data.bytes().tobytes()
                    qimg.loadFromData(byte_data)
                
                ext = Path(self.file_object.name()).suffix.lower()
                if qimg.isNull():
                    self.signals.done.emit(self.file_object.name(), QImage(), ext)
                else:
                    qimg = qimg.scaled(self.size, self.size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.signals.done.emit(self.file_object.name(), qimg, "")
        except Exception:
            try:
                ext = Path(self.file_object.name()).suffix.lower()
                self.signals.done.emit(self.file_object.name(), QImage(), ext)
            except Exception:
                pass

_iphone_thumb_pool = QThreadPool()
_iphone_thumb_pool.setMaxThreadCount(4)
_iphone_thumb_cache = {}
_active_iphone_signals = set()

def get_iphone_thumb_async(file_object, size: int, callback):
    name = file_object.name()
    cache_key = f"{name}_{size}"
    if cache_key in _iphone_thumb_cache:
        callback(name, _iphone_thumb_cache[cache_key])
        return
    sig = IPhoneThumbSignals()
    _active_iphone_signals.add(sig)
    
    def _cb(n, qimg, ext):
        try:
            if not qimg.isNull():
                px = QPixmap.fromImage(qimg)
            else:
                px = make_placeholder_pixmap(ext, size)
            _iphone_thumb_cache[cache_key] = px
            
            if shiboken and hasattr(callback, '__self__'):
                obj = callback.__self__
                if not shiboken.isValid(obj):
                    return
                if not getattr(obj, "_is_active", True):
                    return
            callback(n, px)
        except Exception:
            pass
        finally:
            _active_iphone_signals.discard(sig)
        
    sig.done.connect(_cb, Qt.QueuedConnection)
    loader = IPhoneThumbLoader(file_object, size, sig)
    _iphone_thumb_pool.start(loader)

# ── iPhone Photo Card Widget ─────────────────────────────────────────
class IPhoneCard(QFrame):
    clicked = Signal(object)
    double_clicked = Signal(object)

    def __init__(self, file_object, parent=None):
        super().__init__(parent)
        self.file_object = file_object
        self.selected = False
        self.drag_start_position = QPoint()
        self.setFixedSize(THUMB_SIZE + 16, THUMB_SIZE + 42)
        self.setCursor(Qt.PointingHandCursor)
        self._is_active = True
        self._setup()
        self._load_thumb()

    def _setup(self):
        self._update_style()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 4)
        lay.setSpacing(3)

        self.img_lbl = QLabel(alignment=Qt.AlignCenter)
        self.img_lbl.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.img_lbl.setStyleSheet(f"background:{CARD_BG}; border-radius:6px;")
        self.img_lbl.setScaledContents(True)
        lay.addWidget(self.img_lbl)

        bot = QHBoxLayout()
        bot.setContentsMargins(0,0,0,0)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.dot.setStyleSheet(f"background:{DOT_PENDING}; border-radius:4px;")
        
        self.name_lbl = QLabel()
        self.name_lbl.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:600;")
        self.name_lbl.setMaximumWidth(THUMB_SIZE - 12)
        bot.addWidget(self.dot)
        bot.addWidget(self.name_lbl, 1)
        lay.addLayout(bot)

        nm = self.file_object.name()
        self.name_lbl.setText(nm if len(nm)<=15 else nm[:12]+"…")

    def _load_thumb(self):
        get_iphone_thumb_async(self.file_object, THUMB_SIZE, self._on_thumb)

    def _on_thumb(self, name, px):
        if not getattr(self, "_is_active", True):
            return
        if shiboken and not shiboken.isValid(self):
            return
        try:
            if name == self.file_object.name():
                if shiboken and shiboken.isValid(self.img_lbl):
                    self.img_lbl.setPixmap(px)
        except RuntimeError:
            pass

    def set_downloaded(self, status="done"):
        color = {
            "done": DOT_DONE,
            "copying": DOT_COPY,
            "pending": DOT_PENDING
        }.get(status, DOT_PENDING)
        self.dot.setStyleSheet(f"background:{color}; border-radius:4px;")

    def _update_style(self):
        border_color = ACCENT if self.selected else BORDER
        hover_border = ACCENT if self.selected else SCROLLBAR_HANDLE
        self.setStyleSheet(f"""
            IPhoneCard {{
                background: {PANEL_BG};
                border: 1.5px solid {border_color};
                border-radius: 10px;
            }}
            IPhoneCard:hover {{
                background: {HOVER_BG};
                border-color: {hover_border};
            }}
        """)

    def set_selected(self, v: bool):
        self.selected = v
        self._update_style()

    def mousePressEvent(self, e):
        p = self.parentWidget()
        while p:
            if hasattr(p, "focused"):
                p.focused.emit()
                break
            p = p.parentWidget()

        if e.button() == Qt.LeftButton:
            self.drag_start_position = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            curr_pos = e.position().toPoint()
            if (curr_pos - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
                self.clicked.emit(self)
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.double_clicked.emit(self)
        super().mouseDoubleClickEvent(e)

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(e)
            return
        if (e.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(e)
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData("application/x-iphone-files", b"iphone")
        drag.setMimeData(mime_data)

        pix = self.img_lbl.pixmap()
        if pix and not pix.isNull():
            drag.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            drag.setHotSpot(QPoint(32, 32))

        drag.exec(Qt.CopyAction)

    def contextMenuEvent(self, e):
        self._show_context_menu()
        e.accept()

    def _show_context_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {HEADER};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {ACCENT};
                color: white;
            }}
        """)
        
        info_action = QAction("Get Info", self)
        info_action.triggered.connect(self._show_info)
        
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self._copy_item)

        menu.addAction(info_action)
        menu.addSeparator()
        menu.addAction(copy_action)
        menu.exec(QCursor.pos())

    def _copy_item(self):
        parent_panel = getattr(self, "parent_panel", None)
        if parent_panel and hasattr(parent_panel, "_copy_selected_files"):
            parent_panel._copy_selected_files()

    def _show_info(self):
        dialog = GetInfoDialog(self.file_object, is_iphone=True, parent=self.window())
        dialog.exec()

# ── Sortable Table Widget Item ──────────────────────────────────────────────
class SortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, value):
        super().__init__(text)
        self.value = value
        self.setFlags(self.flags() & ~Qt.ItemIsEditable)

    def __lt__(self, other):
        if isinstance(other, SortableTableWidgetItem):
            if self.value is None or other.value is None:
                return False
            return self.value < other.value
# ── Custom Dual Navigation Pill Widget ────────────────────────────────────────
class NavPillWidget(QWidget):
    back_clicked = Signal()
    fwd_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(49)
        self.setFixedWidth(86)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Go Back (Left) / Go Forward (Right)")
        self.setMouseTracking(True)
        
        self.state = "none"  # "none", "left", "right"
        self.is_hovered = False
        
        self.pix_inactive = None
        self.pix_hover = None
        self.pix_left = None
        self.pix_right = None
        
        self._load_pixmaps()

    def _load_pixmaps(self):
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        w_px = int(86 * dpr)
        h_px = int(49 * dpr)

        path_inactive = get_asset_path("ARW-buttons not active.png")
        path_left = get_asset_path("ARW button clicked left.png")
        path_right = get_asset_path("ARW button clicked right.png")
        path_hover = get_asset_path("ARW-active.png")
        if not os.path.exists(path_hover): path_hover = get_asset_path("ARW-active.jpeg")

        def load_scaled(path):
            if os.path.exists(path):
                px = QPixmap(path).scaled(w_px, h_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                px.setDevicePixelRatio(dpr)
                return px
            return None

        self.pix_inactive = load_scaled(path_inactive)
        self.pix_left = load_scaled(path_left)
        self.pix_right = load_scaled(path_right)
        self.pix_hover = load_scaled(path_hover)

    def set_nav_state(self, can_back, can_fwd):
        self.update()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if event.pos().x() < self.width() / 2:
                self.state = "left"
                self.update()
                self.back_clicked.emit()
            else:
                self.state = "right"
                self.update()
                self.fwd_clicked.emit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.state = "none"
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pix = None
        if self.state == "left" and self.pix_left:
            pix = self.pix_left
        elif self.state == "right" and self.pix_right:
            pix = self.pix_right
        elif self.is_hovered and self.pix_hover:
            pix = self.pix_hover
        else:
            pix = self.pix_inactive
            
        if pix and not pix.isNull():
            dpr = pix.devicePixelRatio() if hasattr(pix, "devicePixelRatio") else 1.0
            pw = int(pix.width() / dpr)
            ph = int(pix.height() / dpr)
            x = (self.width() - pw) // 2
            y = (self.height() - ph) // 2
            painter.drawPixmap(x, y, pix)
        else:
            super().paintEvent(event)

# ── Windows-Style Translucent Blue Rubberband Selection Overlay ──────────────
class SelectionSquareOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        # Windows 11 accent translucent blue fill
        painter.setBrush(QBrush(QColor(10, 132, 255, 65)))
        # Windows 11 crisp blue outline border
        painter.setPen(QPen(QColor(10, 132, 255, 230), 1.5))
        r = self.rect().adjusted(0, 0, -1, -1)
        if r.width() > 0 and r.height() > 0:
            painter.drawRect(r)

# ── RubberBand Grid Widget for Click-and-Drag Multi-Selection ─────────────────
class RubberBandGridWidget(QWidget):
    def __init__(self, file_panel, parent=None):
        super().__init__(parent)
        self.file_panel = file_panel
        self.rubber_band = None
        self.origin = QPoint()
        self.is_rubber_banding = False

    def focusInEvent(self, e):
        if hasattr(self.file_panel, "focused"):
            self.file_panel.focused.emit()
        super().focusInEvent(e)

    def mousePressEvent(self, e):
        if hasattr(self.file_panel, "focused"):
            self.file_panel.focused.emit()
        if e.button() == Qt.LeftButton:
            self.origin = e.pos()
            self.is_rubber_banding = True
            if not self.rubber_band:
                self.rubber_band = SelectionSquareOverlay(self)
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()
            self.rubber_band.raise_()
            
            if not (e.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)):
                self.file_panel.selected_cards.clear()
                for c in getattr(self.file_panel, "_cards", []):
                    c.set_selected(False)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.is_rubber_banding and (e.buttons() & Qt.LeftButton):
            rect = QRect(self.origin, e.pos()).normalized()
            if not self.rubber_band:
                self.rubber_band = SelectionSquareOverlay(self)
            self.rubber_band.setGeometry(rect)
            self.rubber_band.show()
            self.rubber_band.raise_()
            self.rubber_band.update()
            
            for card in getattr(self.file_panel, "_cards", []):
                if card.geometry().intersects(rect):
                    card_obj = getattr(card, "path", getattr(card, "file_object", None))
                    if card_obj:
                        self.file_panel.selected_cards.add(card_obj)
                        card.set_selected(True)
                elif not (e.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)):
                    card_obj = getattr(card, "path", getattr(card, "file_object", None))
                    if card_obj and card_obj in self.file_panel.selected_cards:
                        self.file_panel.selected_cards.remove(card_obj)
                    card.set_selected(False)
            self.file_panel.update_preview()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self.is_rubber_banding and e.button() == Qt.LeftButton:
            if self.rubber_band:
                self.rubber_band.hide()
            self.is_rubber_banding = False
            self.file_panel.update_preview()
        super().mouseReleaseEvent(e)

    def contextMenuEvent(self, e):
        self.file_panel._show_grid_context_menu(e.globalPos())
        e.accept()

# ── Draggable Table Widget for List/Details Mode Drag & Drop ──────────────────
class DraggableTableWidget(QTableWidget):
    def __init__(self, file_panel, parent=None):
        super().__init__(parent)
        self.file_panel = file_panel
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.rubber_band = None
        self.origin = QPoint()
        self.press_item = None
        self.is_rubber_banding = False

    def focusInEvent(self, e):
        if hasattr(self.file_panel, "focused"):
            self.file_panel.focused.emit()
        super().focusInEvent(e)

    def mousePressEvent(self, e):
        if hasattr(self.file_panel, "focused"):
            self.file_panel.focused.emit()
            
        if e.button() == Qt.LeftButton:
            self.origin = e.pos()
            self.press_item = self.itemAt(e.pos())
            self.is_rubber_banding = False
            if self.press_item is None:
                self.is_rubber_banding = True
                if not (e.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)):
                    self.clearSelection()
                    if hasattr(self.file_panel, "selected_cards"):
                        self.file_panel.selected_cards.clear()

        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            if not self.is_rubber_banding and self.press_item is None:
                self.is_rubber_banding = True

            if self.is_rubber_banding:
                rect = QRect(self.origin, e.pos()).normalized()
                if not self.rubber_band:
                    self.rubber_band = SelectionSquareOverlay(self.viewport())
                self.rubber_band.setGeometry(rect)
                self.rubber_band.show()
                self.rubber_band.raise_()
                self.rubber_band.update()

                selection = QItemSelection()
                for row in range(self.rowCount()):
                    row_top = self.rowViewportPosition(row)
                    row_height = self.rowHeight(row)
                    if row_top < -row_height or row_top > self.viewport().height():
                        continue
                    row_rect = QRect(0, row_top, self.viewport().width(), row_height)
                    if row_rect.intersects(rect):
                        top_left = self.model().index(row, 0)
                        bottom_right = self.model().index(row, self.columnCount() - 1)
                        selection.select(top_left, bottom_right)

                flags = QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
                if (e.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)):
                    flags = QItemSelectionModel.Select | QItemSelectionModel.Rows

                self.selectionModel().select(selection, flags)

                if hasattr(self.file_panel, "update_preview"):
                    self.file_panel.update_preview()
                return

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self.is_rubber_banding:
            if self.rubber_band:
                self.rubber_band.hide()
            self.is_rubber_banding = False
            self.press_item = None
            if hasattr(self.file_panel, "update_preview"):
                self.file_panel.update_preview()
            return
        self.press_item = None
        super().mouseReleaseEvent(e)

    def startDrag(self, supportedActions):
        selected_paths = self.file_panel.get_selected()
        if not selected_paths:
            return
        
        drag = QDrag(self)
        mime_data = QMimeData()
        
        if self.file_panel.mode == "iphone":
            mime_data.setData("application/x-iphone-files", b"iphone")
            urls = []
            for file_obj in selected_paths:
                if hasattr(file_obj, "path") and os.path.exists(file_obj.path):
                    urls.append(QUrl.fromLocalFile(file_obj.path))
            if urls:
                mime_data.setUrls(urls)
        else:
            paths_clean = [str(p) for p in selected_paths if str(p) != ".."]
            if not paths_clean:
                return
            paths_data = "\n".join(paths_clean).encode('utf-8')
            mime_data.setData("application/x-local-files", paths_data)
            urls = [QUrl.fromLocalFile(p) for p in paths_clean if os.path.exists(p)]
            if urls:
                mime_data.setUrls(urls)
                
        drag.setMimeData(mime_data)
        drag.exec(Qt.CopyAction | Qt.MoveAction)

# ── Symmetrical File Panel (Left & Right Panels) ──────────────────────────────
class FilePanel(QWidget):
    focused = Signal()
    device_changed = Signal(int)

    def __init__(self, is_left=False, parent=None):
        super().__init__(parent)
        self.is_left = is_left
        self.mode = "local"  # "local" | "iphone"
        self.current_path = os.path.expanduser("~/Pictures")
        
        # History stacks
        self.history = [self.current_path]
        self.history_index = 0
        
        self.media_files = []
        self.selected_cards = set()
        self._filter = "All"
        self._search = ""
        self.view_mode = "details"  # Toggle view mode: "grid" | "details"
        self._cards = []
        self._all_items = []
        
        self.setAcceptDrops(True)
        self._drop_highlight = False
        self._build()
        self.load_path(self.current_path)

    def get_current_file_paths(self):
        paths = []
        items_source = self._all_items if hasattr(self, "_all_items") and self._all_items else getattr(self, "media_files", [])
        for item in items_source:
            if isinstance(item, tuple):
                p, is_dir = item[0], item[1]
                if p != ".." and not is_dir:
                    paths.append(p)
            elif isinstance(item, str):
                if item != "..":
                    paths.append(item)
            elif hasattr(item, "path"):
                paths.append(item.path)
            elif hasattr(item, "name"):
                paths.append(item.name)
        return paths

    def _nav_btn_style(self):
        return f"""
            QPushButton {{
                background: rgba(255,255,255,0.08);
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.18);
            }}
            QPushButton:disabled {{
                color: rgba(255, 255, 255, 0.25);
                background: rgba(255, 255, 255, 0.02);
                border-color: rgba(255, 255, 255, 0.08);
            }}
        """

    def _build(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(4, 4, 4, 4)

        self.container = QFrame()
        self.container.setObjectName("PanelContainer")
        self.set_focused(False)

        lay = QVBoxLayout(self.container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        self.hdr = QFrame()
        self.hdr.setFixedHeight(56)
        if self.is_left:
            self.hdr.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {HDR_LEFT_GRAD}, stop:1 {HEADER}); border-bottom: 1px solid {BORDER}; border-top-left-radius: 6px; border-top-right-radius: 6px;")
        else:
            self.hdr.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {HDR_RIGHT_GRAD}, stop:1 {HEADER}); border-bottom: 1px solid {BORDER}; border-top-left-radius: 6px; border-top-right-radius: 6px;")
        
        hl = QHBoxLayout(self.hdr)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.setSpacing(8)

        # Title Label
        title_str = "Source Destination" if self.is_left else "Local Destination"
        self.title_lbl = QLabel(title_str)
        self.title_lbl.setStyleSheet(f"color:{TITLE_COLOR}; font-size:11px; font-weight:700;")

        hdr_btn_bg = "rgba(0,0,0,0.06)" if CURRENT_THEME_MODE == "light" else "rgba(255,255,255,0.12)"
        hdr_btn_hover = "rgba(0,0,0,0.12)" if CURRENT_THEME_MODE == "light" else "rgba(255,255,255,0.22)"
        hdr_btn_color = "#111827" if CURRENT_THEME_MODE == "light" else "#ffffff"

        self.up_btn = QPushButton("▲")
        self.up_btn.setFixedSize(28, 28)
        self.up_btn.setCursor(Qt.PointingHandCursor)
        self.up_btn.setToolTip("Go Up to parent directory")
        self.up_btn.setStyleSheet(f"""
            QPushButton {{
                background: {hdr_btn_bg};
                color: {hdr_btn_color};
                border: 1px solid {BORDER};
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {hdr_btn_hover};
            }}
            QPushButton:disabled {{
                background: transparent;
                border-color: {HOVER_BG};
            }}
        """)
        self.up_btn.clicked.connect(self._go_up)

        # Custom Dual Navigation Pill & Up button
        self.nav_pill = NavPillWidget(self)
        self.nav_pill.back_clicked.connect(self._go_back)
        self.nav_pill.fwd_clicked.connect(self._go_forward)

        self.back_btn = self.nav_pill
        self.fwd_btn = self.nav_pill

        hl.addWidget(self.nav_pill)
        hl.addWidget(self.up_btn)
        hl.addWidget(self.title_lbl)

        if self.is_left:
            # Add Source Button
            self.add_src_btn = QPushButton("Add Source")
            self.add_src_btn.setFixedHeight(28)
            self.add_src_btn.setCursor(Qt.PointingHandCursor)
            self.add_src_btn.setStyleSheet(f"""
                QPushButton {{ background:{hdr_btn_bg}; color:{hdr_btn_color};
                              border:1px solid {BORDER}; border-radius:6px; padding:5px 12px; font-size:11px; font-weight:600; }}
                QPushButton:hover {{ background:{hdr_btn_hover}; }}
            """)
            self.add_src_btn.clicked.connect(self._show_add_source_menu)
            hl.addWidget(self.add_src_btn)
            
            # Combobox for iPhone/USB devices
            self.device_cb = QComboBox()
            self.device_cb.setFixedHeight(28)
            self.device_cb.setStyleSheet(f"""
                QComboBox {{ background:{INPUT_BG}; color:{TEXT}; border:1px solid {BORDER};
                            border-radius:6px; padding:3px 12px; font-size:11px; min-width:140px; }}
                QComboBox::drop-down {{ border:none; }}
                QComboBox QAbstractItemView {{ background:{INPUT_BG}; color:{TEXT}; selection-background-color:{ACCENT}; }}
            """)
            self.device_cb.addItem("Scan for USB devices…")
            self.device_cb.currentIndexChanged.connect(self.device_changed.emit)
            self.device_cb.hide()
            hl.addWidget(self.device_cb)
        else:
            # Browse Button
            self.browse_btn = QPushButton("Browse…")
            self.browse_btn.setFixedHeight(28)
            self.browse_btn.setCursor(Qt.PointingHandCursor)
            self.browse_btn.setStyleSheet(f"""
                QPushButton {{ background:{hdr_btn_bg}; color:{hdr_btn_color};
                              border:1px solid {BORDER}; border-radius:6px; padding:5px 12px; font-size:11px; font-weight:600; }}
                QPushButton:hover {{ background:{hdr_btn_hover}; }}
            """)
            self.browse_btn.clicked.connect(self._browse)
            hl.addWidget(self.browse_btn)

        hl.addStretch(1)

        # Grid & List View Buttons side by side
        self.grid_btn = QPushButton("Grid")
        self.grid_btn.setFixedHeight(28)
        self.grid_btn.setCursor(Qt.PointingHandCursor)
        self.grid_btn.clicked.connect(lambda: self.set_view_mode("grid"))
        hl.addWidget(self.grid_btn)

        self.list_btn = QPushButton("List")
        self.list_btn.setFixedHeight(28)
        self.list_btn.setCursor(Qt.PointingHandCursor)
        self.list_btn.clicked.connect(lambda: self.set_view_mode("details"))
        hl.addWidget(self.list_btn)

        self.view_btn = self.grid_btn
        self._update_view_button_styles()

        # Preview Toggle Button
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setCheckable(True)
        self.preview_btn.setFixedHeight(28)
        self.preview_btn.setCursor(Qt.PointingHandCursor)
        self.preview_btn.setStyleSheet(f"""
            QPushButton {{ background:{hdr_btn_bg}; color:{hdr_btn_color};
                          border:1px solid {BORDER}; border-radius:6px; padding:5px 12px; font-size:11px; font-weight:600; }}
            QPushButton:hover {{ background:{hdr_btn_hover}; }}
            QPushButton:checked {{ background:{ACCENT}; color:white; border-color:{ACCENT}; }}
        """)
        self.preview_btn.clicked.connect(self._toggle_preview_panel)
        hl.addWidget(self.preview_btn)

        lay.addWidget(self.hdr)

        # Filter bar
        self.fbar = QFrame()
        self.fbar.setFixedHeight(38)
        self.fbar.setStyleSheet(f"background:{HEADER}; border-bottom:1px solid {BORDER};")
        fl = QHBoxLayout(self.fbar)
        fl.setContentsMargins(12, 0, 12, 0)
        fl.setSpacing(8)
        
        self.search_box = QLineEdit()
        self.search_box.setStyleSheet(f"""
            QLineEdit {{ background:{INPUT_BG}; color:{TEXT}; border:1px solid {BORDER};
                        border-radius:5px; padding:3px 8px; font-size:11px; }}
        """)
        self.search_box.textChanged.connect(self._on_search)
        
        self.filter_cb = QComboBox()
        self.filter_cb.addItems(["All", "Photos", "Videos", "RAW"])
        self.filter_cb.setStyleSheet(f"""
            QComboBox {{ background:{INPUT_BG}; color:{TEXT}; border:1px solid {BORDER};
                        border-radius:5px; padding:2px 8px; font-size:11px; min-width:70px; }}
            QComboBox::drop-down {{ border:none; }}
            QComboBox QAbstractItemView {{ background:{INPUT_BG}; color:{TEXT}; selection-background-color:{ACCENT}; }}
        """)
        self.filter_cb.currentTextChanged.connect(self._on_filter)
        
        self.count_lbl = QLabel("0 items")
        self.count_lbl.setStyleSheet(f"color:{SUBTEXT}; font-size:10px;")
        
        self.sel_lbl = QLabel("")
        self.sel_lbl.setStyleSheet(f"color:{ACCENT}; font-size:10px;")
        
        fl.addWidget(self.search_box, 2)
        fl.addWidget(self.filter_cb)
        fl.addWidget(self.count_lbl)
        fl.addWidget(self.sel_lbl)
        lay.addWidget(self.fbar)

        # Content Splitter (Files list on left, side preview on right)
        self.content_splitter = QSplitter(Qt.Horizontal)
        self.content_splitter.setStyleSheet(f"QSplitter::handle {{ background:{BORDER}; width:1px; }}")

        # Files list container
        self.files_container = QWidget()
        files_lay = QVBoxLayout(self.files_container)
        files_lay.setContentsMargins(0, 0, 0, 0)
        files_lay.setSpacing(0)

        # Scroll Area (Grid mode)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"QScrollArea {{ background:{BG}; border:none; }}")
        self.grid_widget = RubberBandGridWidget(self)
        self.grid_widget.setStyleSheet(f"background:{BG};")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(GRID_PAD)
        self.grid_layout.setContentsMargins(GRID_PAD, GRID_PAD, GRID_PAD, GRID_PAD)
        self.scroll.setWidget(self.grid_widget)
        self.scroll.viewport().installEventFilter(self)
        files_lay.addWidget(self.scroll, 1)

        # TableWidget (List/Details mode)
        self.table = DraggableTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Preview", "Name", "Date Modified", "Type", "Size"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {PANEL_BG};
                alternate-background-color: {HOVER_BG};
                color: {TEXT};
                gridline-color: {BORDER};
                border: none;
                font-size: 11px;
            }}
            QTableWidget::item {{
                border-bottom: 1px solid {BORDER};
                padding: 1px 4px;
            }}
            QTableWidget::item:selected {{
                background-color: {ACCENT};
                color: white;
            }}
            QHeaderView::section {{
                background-color: {HEADER};
                color: {SUBTEXT};
                padding: 6px;
                border: none;
                font-weight: bold;
                font-size: 10px;
            }}
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(0, 46)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 70)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)
        self.table.itemSelectionChanged.connect(self.update_preview)
        self.scroll.hide()
        files_lay.addWidget(self.table, 1)

        # Drop overlay label
        self.drop_lbl = QLabel("Drop files here to copy", self)
        self.drop_lbl.setAlignment(Qt.AlignCenter)
        self.drop_lbl.setStyleSheet(f"""
            color:{ACCENT}; font-size:16px; font-weight:600;
            background:rgba(10,132,255,0.12); border:2px dashed {ACCENT};
            border-radius:16px; padding:20px;
        """)
        self.drop_lbl.hide()

        # Side Preview Panel
        self.preview_panel = QFrame()
        self.preview_panel.setStyleSheet(f"background:{PANEL_BG}; border-left:1px solid {BORDER};")
        self.preview_panel.setMinimumWidth(150)
        
        preview_lay = QVBoxLayout(self.preview_panel)
        preview_lay.setContentsMargins(8, 8, 8, 8)
        preview_lay.setSpacing(8)
        
        self.preview_title = QLabel("Preview")
        self.preview_title.setAlignment(Qt.AlignCenter)
        self.preview_title.setStyleSheet(f"color:{TITLE_COLOR}; font-size:11px; font-weight:bold; border-bottom:1px solid {BORDER}; padding-bottom:4px;")
        preview_lay.addWidget(self.preview_title)
        
        self.preview_placeholder = QLabel("Select a file to preview")
        self.preview_placeholder.setAlignment(Qt.AlignCenter)
        self.preview_placeholder.setStyleSheet(f"color:{SUBTEXT}; font-size:11px;")
        self.preview_placeholder.setWordWrap(True)
        preview_lay.addWidget(self.preview_placeholder, 1)
        
        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setStyleSheet(f"background:{PREVIEW_BG}; border-radius:4px;")
        self.preview_image.setScaledContents(False)
        self.preview_image.hide()
        preview_lay.addWidget(self.preview_image, 1)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet(f"background:{PREVIEW_BG}; color:{TEXT}; border:none; border-radius:4px; font-family:monospace; font-size:10px;")
        self.preview_text.hide()
        preview_lay.addWidget(self.preview_text, 1)

        if HAS_QT_MULTIMEDIA:
            self.video_player = NativeVideoPlayerWidget()
            self.video_player.hide()
            preview_lay.addWidget(self.video_player, 1)

        self.preview_gps_lbl = QLabel()
        self.preview_gps_lbl.setStyleSheet("color:#8e8e93; font-size:10px; font-weight:400; background:transparent; padding:2px 4px;")
        self.preview_gps_lbl.setWordWrap(True)
        self.preview_gps_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.preview_gps_lbl.hide()
        preview_lay.addWidget(self.preview_gps_lbl)

        # Assemble Splitter
        self.content_splitter.addWidget(self.files_container)
        self.content_splitter.addWidget(self.preview_panel)
        self.content_splitter.setSizes([450, 200])
        self.content_splitter.splitterMoved.connect(self._on_splitter_moved)
        self.preview_panel.hide()

        lay.addWidget(self.content_splitter, 1)
        main_lay.addWidget(self.container)
        self._install_focus_event_filters()

    def _install_focus_event_filters(self):
        """Install event filters recursively on all child widgets to capture clicks anywhere in empty space or controls."""
        self._install_focus_filter_recursive(self)

    def _install_focus_filter_recursive(self, widget):
        if not widget:
            return
        try:
            widget.installEventFilter(self)
        except Exception:
            pass
        for child in widget.findChildren(QWidget):
            try:
                child.installEventFilter(self)
            except Exception:
                pass

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick, QEvent.FocusIn):
            self.focused.emit()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        self.focused.emit()
        super().mousePressEvent(event)

    def set_focused(self, is_focused):
        border_color = ACCENT if is_focused else BORDER
        self.container.setStyleSheet(f"""
            #PanelContainer {{
                border: 2px solid {border_color};
                border-radius: 8px;
                background: {BG};
            }}
        """)

    def _restyle(self):
        """Re-apply all stylesheets using current theme globals. Called on theme switch."""
        hdr_btn_bg = "rgba(0,0,0,0.06)" if CURRENT_THEME_MODE == "light" else "rgba(255,255,255,0.12)"
        hdr_btn_hover = "rgba(0,0,0,0.12)" if CURRENT_THEME_MODE == "light" else "rgba(255,255,255,0.22)"
        hdr_btn_color = "#111827" if CURRENT_THEME_MODE == "light" else "#ffffff"

        # Header gradient
        if self.is_left:
            self.hdr.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {HDR_LEFT_GRAD}, stop:1 {HEADER}); border-bottom: 1px solid {BORDER}; border-top-left-radius: 6px; border-top-right-radius: 6px;")
        else:
            self.hdr.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {HDR_RIGHT_GRAD}, stop:1 {HEADER}); border-bottom: 1px solid {BORDER}; border-top-left-radius: 6px; border-top-right-radius: 6px;")
        
        self.title_lbl.setStyleSheet(f"color:{TITLE_COLOR}; font-size:11px; font-weight:700;")

        # Up button
        round_nav_style = f"""
            QPushButton {{
                background: {hdr_btn_bg};
                color: {hdr_btn_color};
                border: 1px solid {BORDER};
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {hdr_btn_hover};
            }}
            QPushButton:disabled {{
                background: transparent;
                color: {SUBTEXT};
                border: 1px solid transparent;
            }}
        """
        if hasattr(self, "nav_pill"):
            self.nav_pill._load_pixmaps()
            self.nav_pill.update()

        # View / Preview buttons
        self._update_view_button_styles()
        self.preview_btn.setStyleSheet(f"""
            QPushButton {{ background:{hdr_btn_bg}; color:{TITLE_COLOR};
                          border:1px solid {BORDER}; border-radius:6px; padding:5px 12px; font-size:11px; font-weight:600; }}
            QPushButton:hover {{ background:{hdr_btn_hover}; }}
            QPushButton:checked {{ background:{ACCENT}; color:white; border-color:{ACCENT}; }}
        """)

        # Filter bar
        self.fbar.setStyleSheet(f"background:{HEADER}; border-bottom:1px solid {BORDER};")
        self.search_box.setStyleSheet(f"""
            QLineEdit {{ background:{INPUT_BG}; color:{TEXT}; border:1px solid {BORDER};
                        border-radius:5px; padding:3px 8px; font-size:11px; }}
        """)
        self.filter_cb.setStyleSheet(f"""
            QComboBox {{ background:{INPUT_BG}; color:{TEXT}; border:1px solid {BORDER};
                        border-radius:5px; padding:2px 8px; font-size:11px; min-width:70px; }}
            QComboBox::drop-down {{ border:none; }}
            QComboBox QAbstractItemView {{ background:{INPUT_BG}; color:{TEXT}; selection-background-color:{ACCENT}; }}
        """)
        self.count_lbl.setStyleSheet(f"color:{SUBTEXT}; font-size:10px;")
        self.sel_lbl.setStyleSheet(f"color:{ACCENT}; font-size:10px;")

        # Content areas
        self.content_splitter.setStyleSheet(f"QSplitter::handle {{ background:{BORDER}; width:1px; }}")
        self.scroll.setStyleSheet(f"QScrollArea {{ background:{BG}; border:none; }}")
        self.grid_widget.setStyleSheet(f"background:{BG};")

        # Table
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {PANEL_BG};
                alternate-background-color: {HOVER_BG};
                color: {TEXT};
                gridline-color: {BORDER};
                border: none;
                font-size: 11px;
            }}
            QTableWidget::item {{
                border-bottom: 1px solid {BORDER};
                padding: 1px 4px;
            }}
            QTableWidget::item:selected {{
                background-color: {ACCENT};
                color: white;
            }}
            QHeaderView {{
                background-color: {HEADER};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {HEADER};
                color: {TEXT};
                padding: 6px;
                border-bottom: 1px solid {BORDER};
                border-right: 1px solid {BORDER};
                font-weight: bold;
                font-size: 10px;
            }}
            QTableCornerButton::section {{
                background-color: {HEADER};
                border: none;
            }}
        """)

        # Drop overlay
        self.drop_lbl.setStyleSheet(f"""
            color:{ACCENT}; font-size:16px; font-weight:600;
            background:rgba(10,132,255,0.12); border:2px dashed {ACCENT};
            border-radius:16px; padding:20px;
        """)

        # Preview panel
        self.preview_panel.setStyleSheet(f"background:{PANEL_BG}; border-left:1px solid {BORDER};")
        self.preview_title.setStyleSheet(f"color:{TITLE_COLOR}; font-size:11px; font-weight:bold; border-bottom:1px solid {BORDER}; padding-bottom:4px;")
        self.preview_placeholder.setStyleSheet(f"color:{SUBTEXT}; font-size:11px;")
        self.preview_image.setStyleSheet(f"background:{PREVIEW_BG}; border-radius:4px;")
        self.preview_text.setStyleSheet(f"background:{PREVIEW_BG}; color:{TEXT}; border:none; border-radius:4px; font-family:monospace; font-size:10px;")

        # Container
        self.set_focused(False)

        # Rebuild cards with new theme
        self.refresh()

    def mousePressEvent(self, e):
        self.focused.emit()
        super().mousePressEvent(e)

    def set_view_mode(self, mode):
        target = "details" if mode in ("details", "list") else "grid"
        if self.view_mode != target:
            if target == "details":
                self.view_mode = "details"
                self.scroll.hide()
                self.table.show()
            else:
                self.view_mode = "grid"
                self.scroll.show()
                self.table.hide()
            self._update_view_button_styles()
            self.refresh()
            mw = self.window()
            if mw and hasattr(mw, "_update_slider_visibility"):
                mw._update_slider_visibility()

    def _update_view_button_styles(self):
        hdr_btn_bg = "rgba(0,0,0,0.06)" if CURRENT_THEME_MODE == "light" else "rgba(255,255,255,0.12)"
        hdr_btn_hover = "rgba(0,0,0,0.12)" if CURRENT_THEME_MODE == "light" else "rgba(255,255,255,0.22)"
        hdr_btn_color = "#111827" if CURRENT_THEME_MODE == "light" else "#ffffff"

        grid_active = (self.view_mode == "grid")
        
        if hasattr(self, "grid_btn"):
            self.grid_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {ACCENT if grid_active else hdr_btn_bg};
                    color: {"white" if grid_active else hdr_btn_color};
                    border: 1px solid {ACCENT if grid_active else BORDER};
                    border-radius: 5px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {ACCENT if grid_active else hdr_btn_hover};
                }}
            """)
            
        if hasattr(self, "list_btn"):
            self.list_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {ACCENT if not grid_active else hdr_btn_bg};
                    color: {"white" if not grid_active else hdr_btn_color};
                    border: 1px solid {ACCENT if not grid_active else BORDER};
                    border-radius: 5px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {ACCENT if not grid_active else hdr_btn_hover};
                }}
            """)

    def _toggle_view_mode(self):
        if self.view_mode == "grid":
            self.set_view_mode("details")
        else:
            self.set_view_mode("grid")

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Select Destination Folder", self.current_path)
        if d:
            self.navigate_to_path(d)

    def _go_up(self):
        parent_path = str(Path(self.current_path).parent)
        if os.path.exists(parent_path) and parent_path != self.current_path:
            self.navigate_to_path(parent_path)

    def load_path(self, path: str):
        path = os.path.abspath(path)
        self.mode = "local"
        self.current_path = path
        
        self.search_box.setPlaceholderText(path)
        
        if self.is_left:
            self.device_cb.hide()
            self.add_src_btn.show()

        # Small Title
        self.title_lbl.setText("Source: " + os.path.basename(path) if self.is_left else "Local: " + os.path.basename(path))

        self.selected_cards.clear()
        self.refresh()
        self.update_preview()
        self._update_nav_buttons()

    def navigate_to_path(self, path: str):
        path = os.path.abspath(path)
        if path == self.current_path:
            return
        self.history = self.history[:self.history_index + 1]
        self.history.append(path)
        self.history_index = len(self.history) - 1
        
        self.load_path(path)
        self._update_nav_buttons()

    def _go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.load_path(self.history[self.history_index])
            self._update_nav_buttons()

    def _go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.load_path(self.history[self.history_index])
            self._update_nav_buttons()

    def _go_up(self):
        if self.mode in ("iphone", "android"):
            return
        parent_path = os.path.dirname(os.path.abspath(self.current_path))
        if os.path.exists(parent_path) and parent_path != self.current_path:
            self.navigate_to_path(parent_path)

    def _update_nav_buttons(self):
        if hasattr(self, "nav_pill"):
            self.nav_pill.set_nav_state(self.history_index > 0, self.history_index < len(self.history) - 1)

        if self.mode in ("iphone", "android"):
            self.up_btn.setEnabled(False)
        else:
            parent_path = os.path.dirname(os.path.abspath(self.current_path))
            self.up_btn.setEnabled(os.path.exists(parent_path) and parent_path != self.current_path)

        mw = self.window()
        if mw and hasattr(mw, "_update_middle_nav_buttons"):
            mw._update_middle_nav_buttons()

    def _show_add_source_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {HEADER};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {ACCENT};
                color: white;
            }}
        """)
        
        folder_action = QAction("📁 Select Local Folder...", self)
        folder_action.triggered.connect(self._browse)
        menu.addAction(folder_action)
        
        scan_action = QAction("📱 iPhone / iOS USB Devices", self)
        scan_action.triggered.connect(self._enable_device_mode)
        menu.addAction(scan_action)

        android_action = QAction("🤖 Android Device (USB / ADB)", self)
        android_action.triggered.connect(self._enable_android_mode)
        menu.addAction(android_action)
        
        menu.exec(QCursor.pos())

    def _enable_device_mode(self):
        self.mode = "iphone"
        self.title_lbl.setText("Source: iPhone")
        self.add_src_btn.show()
        self.device_cb.show()
        self.history = []
        self.history_index = -1
        self._update_nav_buttons()
        self.search_box.setPlaceholderText("Search iPhone media…")
        
        mw = self.window()
        if mw and hasattr(mw, "_start_device_scanning"):
            mw._start_device_scanning()
        elif mw and hasattr(mw, "_refresh_both"):
            mw._refresh_both()

    def _enable_android_mode(self):
        self.mode = "android"
        self.title_lbl.setText("Source: Android Device")
        self.add_src_btn.show()
        self.device_cb.show()
        self.history = []
        self.history_index = -1
        self._update_nav_buttons()
        self.search_box.setPlaceholderText("Search Android media…")
        
        mw = self.window()
        if mw and hasattr(mw, "_start_android_scanning"):
            mw._start_android_scanning()
        elif mw and hasattr(mw, "_refresh_both"):
            mw._refresh_both()

    def refresh(self):
        if self.mode == "iphone":
            mw = self.window()
            if mw and hasattr(mw, "_start_device_scanning"):
                mw._start_device_scanning()
            return
        elif self.mode == "android":
            mw = self.window()
            if mw and hasattr(mw, "_start_android_scanning"):
                mw._start_android_scanning()
            return
        if not self.current_path: return
        p = Path(self.current_path)
        items = []

        if p.parent and p.parent != p:
            items.append(("..", True))

        try:
            if p.exists():
                for item in sorted(p.iterdir()):
                    if item.is_dir() and not item.name.startswith('.'):
                        items.append((str(item), True))
                for item in sorted(p.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                    if item.is_file() and item.suffix.lower() in EXTS:
                        items.append((str(item), False))
        except Exception:
            pass

        self._all_items = items
        self._rebuild()

    def _filtered_items(self):
        f = self._filter
        s = self._search.lower()
        out = []
        for path, is_folder in self._all_items:
            if path == "..":
                out.append((path, is_folder))
                continue
                
            name = Path(path).name.lower()
            ext = Path(path).suffix.lower()
            
            if not is_folder:
                if f == "Photos" and ext in VIDEO_EXTS: continue
                if f == "Videos" and ext not in VIDEO_EXTS: continue
                if f == "RAW" and ext not in {".raw",".cr2",".nef",".arw",".dng"}: continue
            
            if s and s not in name: continue
            out.append((path, is_folder))
        return out

    def _filtered_files(self):
        f = self._filter
        s = self._search.lower()
        out = []
        for file_obj in self.media_files:
            ext = Path(file_obj.name()).suffix.lower()
            if f == "Photos" and ext in VIDEO_EXTS: continue
            if f == "Videos" and ext not in VIDEO_EXTS: continue
            if f == "RAW" and ext not in {".raw",".cr2",".nef",".arw",".dng"}: continue
            if s and s not in file_obj.name().lower(): continue
            out.append(file_obj)
        return out

    def _update_status_labels(self, async_folder_size=None):
        """Update count_lbl and sel_lbl in top-right corner of panel with item count & MB/GB data size."""
        try:
            if self.mode == "local":
                items = self._filtered_items()
                real_items = [it for it in items if it[0] != ".."]
                item_count = len(real_items)
                
                direct_bytes = 0
                has_dirs = False
                for p, is_dir in real_items:
                    if is_dir:
                        has_dirs = True
                    else:
                        try:
                            direct_bytes += os.path.getsize(p)
                        except Exception:
                            pass

                if async_folder_size is not None:
                    sz_str = format_size(async_folder_size)
                elif not has_dirs:
                    sz_str = format_size(direct_bytes)
                else:
                    sz_str = f"~{format_size(direct_bytes)}" if direct_bytes > 0 else ""

                if item_count == 0:
                    self.count_lbl.setText("0 items")
                else:
                    self.count_lbl.setText(f"{item_count} items ({sz_str})" if sz_str else f"{item_count} items")

                if self.selected_cards:
                    sel_count = len(self.selected_cards)
                    sel_bytes = 0
                    for sel in self.selected_cards:
                        if isinstance(sel, str) and sel != "..":
                            if os.path.isfile(sel):
                                try: sel_bytes += os.path.getsize(sel)
                                except Exception: pass
                            elif os.path.isdir(sel):
                                try:
                                    for r, _, files in os.walk(sel):
                                        for f in files:
                                            try: sel_bytes += os.path.getsize(os.path.join(r, f))
                                            except Exception: pass
                                except Exception: pass
                    sel_sz_str = format_size(sel_bytes)
                    self.sel_lbl.setText(f"{sel_count} selected ({sel_sz_str})" if sel_sz_str else f"{sel_count} selected")
                else:
                    self.sel_lbl.setText("")
            else:
                files = self._filtered_files()
                total_bytes = 0
                for f in files:
                    if hasattr(f, "fileSize") and f.fileSize():
                        try: total_bytes += f.fileSize()
                        except Exception: pass

                sz_str = format_size(total_bytes)
                self.count_lbl.setText(f"{len(files)} files ({sz_str})" if sz_str else f"{len(files)} files")

                if self.selected_cards:
                    sel_count = len(self.selected_cards)
                    sel_bytes = 0
                    for sel in self.selected_cards:
                        if hasattr(sel, "fileSize") and sel.fileSize():
                            try: sel_bytes += sel.fileSize()
                            except Exception: pass
                    sel_sz_str = format_size(sel_bytes)
                    self.sel_lbl.setText(f"{sel_count} selected ({sel_sz_str})" if sel_sz_str else f"{sel_count} selected")
                else:
                    self.sel_lbl.setText("")
        except Exception as e:
            print(f"Error updating status labels: {e}")

    def _start_async_folder_size_calc(self):
        if getattr(self, "mode", "local") != "local" or not getattr(self, "current_path", None):
            return
        if not os.path.isdir(self.current_path):
            return
        sig = FolderSizeSignals()
        sig.done.connect(self._on_async_folder_size_done)
        worker = FolderSizeWorker(self.current_path, sig)
        QThreadPool.globalInstance().start(worker)

    def _on_async_folder_size_done(self, path, total_bytes):
        if hasattr(self, "current_path") and self.current_path == path:
            self._update_status_labels(async_folder_size=total_bytes)

    def _rebuild(self):
        # Mark all existing cards as inactive
        for c in self._cards:
            c._is_active = False
            c.deleteLater()
        self._cards.clear()
        
        # Mark all table preview widgets as inactive
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 0)
            if w:
                w._is_active = False
                
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w._is_active = False
                w.deleteLater()
            
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        self._update_status_labels()

        if self.mode == "local":
            items = self._filtered_items()

            if self.view_mode == "grid":
                cols = max(1, (self.scroll.viewport().width() - GRID_PAD*2) // (THUMB_SIZE + 16 + GRID_PAD))
                for i, (path, is_folder) in enumerate(items):
                    card = LocalCard(path, is_folder=is_folder)
                    card.clicked.connect(self._on_card_clicked)
                    card.double_clicked.connect(self._on_card_double_clicked)
                    
                    if path in self.selected_cards:
                        card.set_selected(True)
                        
                    self.grid_layout.addWidget(card, i // cols, i % cols)
                    self._cards.append(card)
                    card.show()
                self.grid_layout.setRowStretch(max(1, len(items)//cols + 1), 1)
            else:
                self.table.setRowCount(len(items))
                for i, (path, is_folder) in enumerate(items):
                    preview = TablePreviewWidget(path, is_folder=is_folder)
                    self.table.setCellWidget(i, 0, preview)

                    name_str = ".. (Go Up)" if path == ".." else Path(path).name
                    self.table.setItem(i, 1, SortableTableWidgetItem(name_str, name_str.lower()))

                    date_str = ""
                    date_val = 0.0
                    if path != "..":
                        try:
                            mtime = Path(path).stat().st_mtime
                            date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                            date_val = mtime
                        except Exception: pass
                    self.table.setItem(i, 2, SortableTableWidgetItem(date_str, date_val))

                    t_str = "Folder" if is_folder else Path(path).suffix.upper().replace(".", "")
                    if path == "..": t_str = ""
                    self.table.setItem(i, 3, SortableTableWidgetItem(t_str, t_str.lower()))

                    sz_str = ""
                    sz_val = -1
                    if not is_folder and path != "..":
                        try:
                            size = Path(path).stat().st_size
                            sz_str = format_size(size)
                            sz_val = size
                        except Exception: pass
                    self.table.setItem(i, 4, SortableTableWidgetItem(sz_str, sz_val))
        else:
            files = self._filtered_files()
            self.count_lbl.setText(f"{len(files)} files")
            self.sel_lbl.setText(f"{len(self.selected_cards)} selected" if self.selected_cards else "")

            if self.view_mode == "grid":
                cols = max(1, (self.scroll.viewport().width() - GRID_PAD*2) // (THUMB_SIZE + 16 + GRID_PAD))
                for i, file_obj in enumerate(files):
                    card = IPhoneCard(file_obj)
                    card.clicked.connect(self._on_card_clicked)
                    card.double_clicked.connect(self._on_card_double_clicked)
                    
                    if file_obj in self.selected_cards:
                        card.set_selected(True)
                        
                    self.grid_layout.addWidget(card, i // cols, i % cols)
                    self._cards.append(card)
                    card.show()
                self.grid_layout.setRowStretch(max(1, len(files)//cols + 1), 1)
            else:
                self.table.setRowCount(len(files))
                for i, file_obj in enumerate(files):
                    preview = TablePreviewWidget(file_obj, is_iphone=True)
                    self.table.setCellWidget(i, 0, preview)

                    name_str = file_obj.name()
                    self.table.setItem(i, 1, SortableTableWidgetItem(name_str, name_str.lower()))

                    date_str = ""
                    date_val = 0.0
                    if hasattr(file_obj, "creationDate") and file_obj.creationDate():
                        try:
                            cd = file_obj.creationDate()
                            date_str = str(cd)[:16]
                            date_val = datetime.strptime(str(cd)[:19], "%Y-%m-%d %H:%M:%S").timestamp()
                        except Exception:
                            date_val = float(i)
                    self.table.setItem(i, 2, SortableTableWidgetItem(date_str, date_val))

                    ext = Path(name_str).suffix.upper().replace(".", "")
                    self.table.setItem(i, 3, SortableTableWidgetItem(ext, ext.lower()))

                    sz_str = ""
                    sz_val = -1
                    if hasattr(file_obj, "fileSize") and file_obj.fileSize():
                        size = file_obj.fileSize()
                        sz_str = format_size(size)
                        sz_val = size
                    self.table.setItem(i, 4, SortableTableWidgetItem(sz_str, sz_val))
                    
        self.table.setSortingEnabled(True)
        self._start_async_folder_size_calc()

    def _on_card_clicked(self, card):
        self.focused.emit()
        if self.mode == "local":
            if card.path == "..": return
            mods = QApplication.keyboardModifiers()
            if not (mods & Qt.ControlModifier or mods & Qt.ShiftModifier):
                self.selected_cards.clear()
                for c in self._cards:
                    c.set_selected(False)
            
            if card.path in self.selected_cards:
                card.set_selected(False)
                self.selected_cards.discard(card.path)
            else:
                card.set_selected(True)
                self.selected_cards.add(card.path)
        else:
            mods = QApplication.keyboardModifiers()
            if not (mods & Qt.ControlModifier or mods & Qt.ShiftModifier):
                self.selected_cards.clear()
                for c in self._cards:
                    c.set_selected(False)
            
            if card.file_object in self.selected_cards:
                card.set_selected(False)
                self.selected_cards.discard(card.file_object)
            else:
                card.set_selected(True)
                self.selected_cards.add(card.file_object)
                
        self._update_status_labels()
        self.update_preview()

    def _set_selection(self, path, select):
        # Kept for compatibility with drop operations
        if select:
            self.selected_cards.add(path)
        else:
            self.selected_cards.discard(path)
        for c in self._cards:
            if c.path == path:
                c.set_selected(select)
        self._update_status_labels()
        self.update_preview()

    def _on_card_double_clicked(self, card):
        if card.is_folder:
            if card.path == "..":
                self._go_up()
            else:
                self.navigate_to_path(card.path)
        else:
            mw = self.window()
            if mw and hasattr(mw, "open_dark_quicklook"):
                mw.open_dark_quicklook(self, card.path if self.mode == "local" else card.file_object)

    def _on_table_double_clicked(self, row, col):
        if self.mode == "local":
            items = self._filtered_items()
            if 0 <= row < len(items):
                path, is_folder = items[row]
                if is_folder:
                    if path == "..":
                        self._go_up()
                    else:
                        self.navigate_to_path(path)
                else:
                    mw = self.window()
                    if mw and hasattr(mw, "open_dark_quicklook"):
                        mw.open_dark_quicklook(self, path)
        else:
            mw = self.window()
            if mw and hasattr(mw, "open_dark_quicklook"):
                filtered = self._filtered_files()
                if 0 <= row < len(filtered):
                    mw.open_dark_quicklook(self, filtered[row])

    def _copy_selected_files(self):
        mw = self.window()
        if not mw: return
        
        if self.mode == "iphone":
            files = self.get_selected()
            if files:
                mw.clipboard_files = [("iphone", f) for f in files]
                if hasattr(mw, "speech_bubble"):
                    mw.speech_bubble.setText(f"Copied {len(files)} iPhone file(s) to clipboard. Right-click destination panel and select Paste.")
        else:
            selected = self.get_selected()
            if selected:
                mw.clipboard_files = [("local", p) for p in selected]
                mime = QMimeData()
                urls = [QUrl.fromLocalFile(p) for p in selected if os.path.exists(p)]
                mime.setUrls(urls)
                QApplication.clipboard().setMimeData(mime)
                if hasattr(mw, "speech_bubble"):
                    mw.speech_bubble.setText(f"Copied {len(selected)} local file(s) to clipboard. Right-click destination panel and select Paste.")

    def _paste_files_here(self):
        mw = self.window()
        if not mw: return
        
        dest_dir = self.current_path
        if self.mode == "iphone":
            QMessageBox.information(self, "Read Only", "iPhone camera rolls are read-only. You cannot paste files onto the iPhone.")
            return

        clip = getattr(mw, "clipboard_files", [])
        if not clip:
            mime = QApplication.clipboard().mimeData()
            if mime.hasUrls():
                clip = [("local", u.toLocalFile()) for u in mime.urls() if u.toLocalFile()]
                
        if not clip:
            QMessageBox.information(self, "Clipboard Empty", "No files in clipboard to paste.")
            return

        dest_name = os.path.basename(dest_dir) or dest_dir
        reply = ask_user_confirmation(
            self,
            "Confirm Paste",
            f"Are you sure you want to copy {len(clip)} item(s) into '{dest_name}'?"
        )
        if reply != QMessageBox.Yes:
            return

        iphone_files = [item[1] for item in clip if item[0] == "iphone"]
        local_paths = [item[1] for item in clip if item[0] == "local"]

        if iphone_files and hasattr(mw, "_start_download_queue"):
            mw._start_download_queue(iphone_files, custom_dest=dest_dir)

        if local_paths:
            self.copy_local_items(local_paths, dest_dir)
            if getattr(mw, "clipboard_cut", False):
                for p_src in local_paths:
                    try:
                        if os.path.exists(p_src) and os.path.abspath(p_src) != os.path.abspath(os.path.join(dest_dir, os.path.basename(p_src))):
                            if os.path.isdir(p_src):
                                shutil.rmtree(p_src)
                            else:
                                os.unlink(p_src)
                    except Exception as e:
                        print(f"Error removing source cut file {p_src}: {e}")
                mw.clipboard_cut = False
                if hasattr(mw, "speech_bubble"):
                    mw.speech_bubble.setText(f"Moved {len(local_paths)} item(s) into '{dest_name}'.")

    def _cut_selected_files(self):
        mw = self.window()
        if not mw: return
        selected = self.get_selected()
        if selected and self.mode == "local":
            mw.clipboard_files = [("local", p) for p in selected]
            mw.clipboard_cut = True
            mime = QMimeData()
            urls = [QUrl.fromLocalFile(p) for p in selected if os.path.exists(p)]
            mime.setUrls(urls)
            QApplication.clipboard().setMimeData(mime)
            if hasattr(mw, "speech_bubble"):
                mw.speech_bubble.setText(f"Cut {len(selected)} item(s) to clipboard. Paste to move them.")

    def _on_table_context_menu(self, pos):
        self._show_grid_context_menu(self.table.viewport().mapToGlobal(pos))

    def _show_grid_context_menu(self, global_pos):
        selected = self.get_selected()
        is_iphone = (self.mode == "iphone")
        
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {HEADER};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {ACCENT};
                color: white;
            }}
        """)

        if len(selected) == 1:
            item = selected[0]
            info_action = QAction("Get Info", self)
            info_action.triggered.connect(lambda: self._show_info_for_item(item, is_iphone=is_iphone))
            menu.addAction(info_action)
            menu.addSeparator()
        elif len(selected) > 1:
            sel_info = QAction(f"ℹ️ {len(selected)} items selected", self)
            sel_info.setEnabled(False)
            menu.addAction(sel_info)
            menu.addSeparator()

        copy_action = QAction("📋 Copy", self)
        copy_action.triggered.connect(self._copy_selected_files)
        copy_action.setEnabled(len(selected) > 0)
        menu.addAction(copy_action)

        if not is_iphone:
            cut_action = QAction("✂️ Cut", self)
            cut_action.triggered.connect(self._cut_selected_files)
            cut_action.setEnabled(len(selected) > 0)
            menu.addAction(cut_action)

            new_folder_action = QAction("📁 Create New Folder", self)
            new_folder_action.triggered.connect(self._create_new_folder)
            menu.addAction(new_folder_action)

            paste_action = QAction("📥 Paste Files Here", self)
            paste_action.triggered.connect(self._paste_files_here)
            mw = self.window()
            has_clip = bool(getattr(mw, "clipboard_files", None) or QApplication.clipboard().mimeData().hasUrls())
            paste_action.setEnabled(has_clip)
            menu.addAction(paste_action)

            if len(selected) > 0:
                menu.addSeparator()
                rename_action = QAction("✏️ Rename" if len(selected) == 1 else "✏️ Batch Rename Selected...", self)
                rename_action.triggered.connect(self._rename_selected_items)
                menu.addAction(rename_action)
                
                delete_action = QAction("🗑️ Delete Selected", self)
                delete_action.triggered.connect(self._delete_selected_items)
                menu.addAction(delete_action)

        menu.exec(global_pos)

    def _create_new_folder(self):
        if self.mode != "local":
            return
        text, ok = QInputDialog.getText(
            self, "Create New Folder", "Enter directory name:"
        )
        if ok and text:
            target_dir = os.path.join(self.current_path, text)
            try:
                os.makedirs(target_dir, exist_ok=True)
                mw = self.window()
                if hasattr(mw, "status_msg"):
                    mw.status_msg.setText(f"Created folder: '{text}' in {os.path.basename(self.current_path)}")
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create directory:\n{e}")

    def _rename_selected_items(self):
        selected = self.get_selected()
        if not selected or self.mode != "local": return
        
        if len(selected) == 1:
            path = selected[0]
            old_name = Path(path).name
            new_name, ok = QInputDialog.getText(
                self, "Rename Item", f"Enter new name for '{old_name}':", text=old_name
            )
            if ok and new_name and new_name != old_name:
                parent_dir = os.path.dirname(path)
                new_path = os.path.join(parent_dir, new_name)
                try:
                    os.rename(path, new_path)
                    self.refresh()
                except Exception as e:
                    QMessageBox.critical(self, "Rename Error", f"Could not rename item:\n{e}")
        else:
            prefix, ok = QInputDialog.getText(
                self, "Batch Rename", f"Enter new prefix/name pattern for {len(selected)} items (e.g. 'Photo_'):", text="Item_"
            )
            if ok and prefix:
                count = 0
                for idx, path in enumerate(selected, 1):
                    if os.path.exists(path):
                        ext = Path(path).suffix
                        parent_dir = os.path.dirname(path)
                        new_name = f"{prefix}{idx}{ext}"
                        new_path = os.path.join(parent_dir, new_name)
                        try:
                            os.rename(path, new_path)
                            count += 1
                        except Exception as e:
                            print(f"Error renaming {path}: {e}")
                self.refresh()
                mw = self.window()
                if mw and hasattr(mw, "speech_bubble"):
                    mw.speech_bubble.setText(f"Renamed {count} item(s) with prefix '{prefix}'.")

    def _delete_selected_items(self):
        selected = self.get_selected()
        if not selected or self.mode != "local": return
        
        if len(selected) == 1:
            name = os.path.basename(selected[0])
            confirm_msg = f"Are you sure you want to permanently delete '{name}'?"
        else:
            confirm_msg = f"Are you sure you want to permanently delete {len(selected)} selected files and folders?"
            
        confirm = ask_user_confirmation(self, "Confirm Delete", confirm_msg)
        if confirm == QMessageBox.Yes:
            deleted_count = 0
            for path in selected:
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.unlink(path)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {path}: {e}")
            self.refresh()
            mw = self.window()
            if mw and hasattr(mw, "speech_bubble"):
                mw.speech_bubble.setText(f"Successfully deleted {deleted_count} item(s).")

    def _show_info_for_item(self, item, is_iphone):
        dialog = GetInfoDialog(item, is_iphone=is_iphone, parent=self.window())
        dialog.exec()

    def get_selected(self):
        if self.view_mode == "details":
            selected_rows = self.table.selectionModel().selectedRows()
            paths_or_files = []
            if self.mode == "local":
                filtered = self._filtered_items()
                for index in selected_rows:
                    row = index.row()
                    if 0 <= row < len(filtered):
                        paths_or_files.append(filtered[row][0])
                return [p for p in paths_or_files if p != ".."]
            else:
                filtered = self._filtered_files()
                for index in selected_rows:
                    row = index.row()
                    if 0 <= row < len(filtered):
                        paths_or_files.append(filtered[row])
                return paths_or_files
        else:
            if self.mode == "local":
                return list(self.selected_cards)
            else:
                return [c.file_object for c in self._cards if c.file_object in self.selected_cards]

    def has_selection(self):
        if self.view_mode == "details":
            return len(self.table.selectionModel().selectedRows()) > 0
        else:
            return len(self.selected_cards) > 0

    def select_path(self, target_path_or_file):
        self.selected_cards.clear()
        target_str = str(target_path_or_file)
        target_base = os.path.basename(target_str)
        
        if self.view_mode == "details":
            self.table.clearSelection()
            if self.mode == "local":
                filtered = self._filtered_items()
                for row, (p, is_folder) in enumerate(filtered):
                    if p == target_str or os.path.basename(p) == target_base:
                        self.table.selectRow(row)
                        item = self.table.item(row, 0)
                        if item:
                            self.table.scrollToItem(item)
                        break
            else:
                filtered = self._filtered_files()
                for row, f in enumerate(filtered):
                    f_name = f.name() if hasattr(f, "name") else str(f)
                    if f == target_path_or_file or f_name == target_str or os.path.basename(f_name) == target_base:
                        self.table.selectRow(row)
                        item = self.table.item(row, 0)
                        if item:
                            self.table.scrollToItem(item)
                        break
            self._update_status_labels()
        else:
            for card in self._cards:
                c_item = card.path if self.mode == "local" else card.file_object
                c_str = str(c_item)
                c_base = os.path.basename(c_str)
                if c_item == target_path_or_file or c_str == target_str or c_base == target_base:
                    card.set_selected(True)
                    self.selected_cards.add(c_item)
                    if hasattr(self, "scroll") and self.scroll:
                        self.scroll.ensureWidgetVisible(card)
                else:
                    card.set_selected(False)
            self.sel_lbl.setText(f"{len(self.selected_cards)} selected" if self.selected_cards else "")
        self.update_preview()

    def select_next_item(self):
        if self.view_mode == "details":
            total = self.table.rowCount()
            if total == 0:
                return
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                next_row = 0
            else:
                curr_row = selected_rows[-1].row()
                next_row = (curr_row + 1) if (curr_row + 1 < total) else 0
            self.table.clearSelection()
            self.table.selectRow(next_row)
            item = self.table.item(next_row, 0)
            if item:
                self.table.setCurrentItem(item)
                self.table.scrollToItem(item)
            self._update_status_labels()
            self.update_preview()
        else:
            if not self._cards:
                return
            selected_indices = [i for i, c in enumerate(self._cards) if getattr(c, "is_selected", False)]
            if not selected_indices:
                next_idx = 0
            else:
                next_idx = (selected_indices[-1] + 1) if (selected_indices[-1] + 1 < len(self._cards)) else 0
            self.selected_cards.clear()
            for i, card in enumerate(self._cards):
                if i == next_idx:
                    card.set_selected(True)
                    c_item = card.path if self.mode == "local" else card.file_object
                    self.selected_cards.add(c_item)
                    if hasattr(self, "scroll") and self.scroll:
                        self.scroll.ensureWidgetVisible(card)
                else:
                    card.set_selected(False)
            self.sel_lbl.setText(f"{len(self.selected_cards)} selected" if self.selected_cards else "")
            self.update_preview()

    def select_prev_item(self):
        if self.view_mode == "details":
            total = self.table.rowCount()
            if total == 0:
                return
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                prev_row = total - 1
            else:
                curr_row = selected_rows[0].row()
                prev_row = (curr_row - 1) if (curr_row - 1 >= 0) else (total - 1)
            self.table.clearSelection()
            self.table.selectRow(prev_row)
            item = self.table.item(prev_row, 0)
            if item:
                self.table.setCurrentItem(item)
                self.table.scrollToItem(item)
            self._update_status_labels()
            self.update_preview()
        else:
            if not self._cards:
                return
            selected_indices = [i for i, c in enumerate(self._cards) if getattr(c, "is_selected", False)]
            if not selected_indices:
                prev_idx = len(self._cards) - 1
            else:
                prev_idx = (selected_indices[0] - 1) if (selected_indices[0] - 1 >= 0) else (len(self._cards) - 1)
            self.selected_cards.clear()
            for i, card in enumerate(self._cards):
                if i == prev_idx:
                    card.set_selected(True)
                    c_item = card.path if self.mode == "local" else card.file_object
                    self.selected_cards.add(c_item)
                    if hasattr(self, "scroll") and self.scroll:
                        self.scroll.ensureWidgetVisible(card)
                else:
                    card.set_selected(False)
            self.sel_lbl.setText(f"{len(self.selected_cards)} selected" if self.selected_cards else "")
            self.update_preview()

    def open_highlighted_item_or_go_forward(self):
        """Open the highlighted folder, preview the highlighted file (.jpg, etc.), or go forward in history."""
        mw = self.window()

        # 1. Details / List mode
        if self.view_mode == "details":
            selected_rows = self.table.selectionModel().selectedRows()
            if selected_rows:
                row = selected_rows[0].row()
                if self.mode == "local":
                    filtered = self._filtered_items()
                    if 0 <= row < len(filtered):
                        path, is_folder = filtered[row]
                        if is_folder:
                            if path == "..":
                                self._go_up()
                                return True
                            elif isinstance(path, str) and os.path.isdir(path):
                                self.navigate_to_path(path)
                                return True
                        else:
                            # It's a file (e.g. .jpg, .png, etc.) -> Open in Preview Window
                            if mw and hasattr(mw, "open_dark_quicklook"):
                                mw.open_dark_quicklook(self, path)
                                return True
                else:
                    filtered = self._filtered_files()
                    if 0 <= row < len(filtered):
                        f = filtered[row]
                        if hasattr(f, "is_folder") and f.is_folder:
                            if hasattr(f, "path") and os.path.isdir(f.path):
                                self.navigate_to_path(f.path)
                                return True
                        else:
                            # iPhone file -> Open in Preview Window
                            if mw and hasattr(mw, "open_dark_quicklook"):
                                mw.open_dark_quicklook(self, f)
                                return True
        else:
            # 2. Grid mode
            selected_cards = [c for c in self._cards if getattr(c, "is_selected", False)]
            if selected_cards:
                card = selected_cards[0]
                if getattr(card, "is_folder", False):
                    if getattr(card, "path", None) == "..":
                        self._go_up()
                        return True
                    elif hasattr(card, "path") and isinstance(card.path, str) and os.path.isdir(card.path):
                        self.navigate_to_path(card.path)
                        return True
                else:
                    # Highlighted file card (.jpg, .png, etc.) -> Open in Preview Window
                    target = card.path if self.mode == "local" else getattr(card, "file_object", None)
                    if target and mw and hasattr(mw, "open_dark_quicklook"):
                        mw.open_dark_quicklook(self, target)
                        return True

        # 3. If no highlighted item, but forward history is available -> go forward in history
        if hasattr(self, "history_index") and hasattr(self, "history") and self.history_index < len(self.history) - 1:
            self._go_forward()
            return True

        return False

    open_selected_folder_or_go_forward = open_highlighted_item_or_go_forward

    def select_all(self):
        self.selected_cards.clear()
        if self.view_mode == "details":
            self.table.selectAll()
        else:
            if self.mode == "local":
                for c in self._cards:
                    if c.path != "..":
                        c.set_selected(True)
                        self.selected_cards.add(c.path)
            else:
                for c in self._cards:
                    c.set_selected(True)
                    self.selected_cards.add(c.file_object)
        self._update_status_labels()
        self.update_preview()

    def deselect_all(self):
        if self.view_mode == "details":
            self.table.clearSelection()
        else:
            for c in self._cards:
                try: c.set_selected(False)
                except RuntimeError: pass
            self.selected_cards.clear()
        self._update_status_labels()
        self.update_preview()

    def _on_filter(self, f): self._filter = f; self._rebuild()
    def _on_search(self, s): self._search = s; self._rebuild()

    def copy_local_items(self, src_paths, dest_dir):
        if not os.path.isdir(dest_dir): return
        mw = self.window()
        copied_count = 0
        overwrite_policy = "ask"

        for p_src in src_paths:
            if not p_src or not os.path.exists(p_src): continue
            if os.path.isdir(p_src) and dest_dir.startswith(p_src): continue
            
            dest = os.path.join(dest_dir, Path(p_src).name)
            if p_src == dest: continue
            
            if os.path.exists(dest):
                if overwrite_policy == "skip_all":
                    continue
                elif overwrite_policy == "ask" and mw and hasattr(mw, "_prompt_overwrite"):
                    choice = mw._prompt_overwrite(Path(p_src).name)
                    if choice == "overwrite_all":
                        overwrite_policy = "overwrite_all"
                    elif choice == "skip_all":
                        overwrite_policy = "skip_all"
                        continue
                    elif choice == "skip":
                        continue

            try:
                if os.path.isdir(p_src):
                    shutil.copytree(p_src, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(p_src, dest)
                copied_count += 1
            except Exception as e:
                print(f"Error copying {p_src}: {e}")
                
        self.refresh()
        if mw and hasattr(mw, "speech_bubble"):
            mw.speech_bubble.setText(f"Successfully copied {copied_count} file(s) to '{os.path.basename(dest_dir) or dest_dir}'.")

    def dragEnterEvent(self, e: QDragEnterEvent):
        if (e.mimeData().hasFormat("application/x-iphone-files") or 
            e.mimeData().hasFormat("application/x-local-files") or 
            e.mimeData().hasUrls()):
            e.acceptProposedAction()
            self._drop_highlight = True
            self.drop_lbl.resize(self.size())
            self.drop_lbl.show()

    def dragLeaveEvent(self, e):
        self._drop_highlight = False
        self.drop_lbl.hide()

    def dropEvent(self, e: QDropEvent):
        self._drop_highlight = False
        self.drop_lbl.hide()
        
        target_dir = self.current_path
        if self.view_mode == "details":
            pos = e.position().toPoint()
            row = self.table.rowAt(pos.y())
            if row >= 0 and self.mode == "local":
                filtered = self._filtered_items()
                if 0 <= row < len(filtered):
                    path, is_folder = filtered[row]
                    if is_folder:
                        target_dir = str(Path(self.current_path).parent) if path == ".." else path

        dest_name = os.path.basename(target_dir) or target_dir

        if e.mimeData().hasFormat("application/x-local-files"):
            paths_str = e.mimeData().data("application/x-local-files").data().decode('utf-8')
            paths = [p for p in paths_str.split("\n") if p]
            if paths:
                reply = ask_user_confirmation(
                    self,
                    "Confirm Drag & Drop Copy",
                    f"Are you sure you want to copy {len(paths)} item(s) into '{dest_name}'?"
                )
                if reply == QMessageBox.Yes:
                    self.copy_local_items(paths, target_dir)
                    e.acceptProposedAction()
        elif e.mimeData().hasFormat("application/x-iphone-files"):
            mw = self.window()
            if mw and hasattr(mw, "_start_download_queue"):
                files = mw.iphone_panel.get_selected()
                if files:
                    reply = ask_user_confirmation(
                        self,
                        "Confirm Drag & Drop Copy",
                        f"Are you sure you want to copy {len(files)} iPhone file(s) into '{dest_name}'?"
                    )
                    if reply == QMessageBox.Yes:
                        mw._start_download_queue(files, custom_dest=target_dir)
                        e.acceptProposedAction()
        elif e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile() and os.path.exists(u.toLocalFile())]
            if paths:
                reply = ask_user_confirmation(
                    self,
                    "Confirm Drag & Drop Copy",
                    f"Are you sure you want to copy {len(paths)} item(s) into '{dest_name}'?"
                )
                if reply == QMessageBox.Yes:
                    self.copy_local_items(paths, target_dir)
                    e.acceptProposedAction()

    def eventFilter(self, obj, event):
        if hasattr(self, "scroll") and self.scroll and obj == self.scroll.viewport():
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.focused.emit()
                self._rubber_origin = event.pos()
                if not hasattr(self, "_rubber_band") or not self._rubber_band:
                    self._rubber_band = QRubberBand(QRubberBand.Rectangle, self.scroll.viewport())
                self._rubber_band.setGeometry(QRect(self._rubber_origin, QSize()))
                self._rubber_band.show()
                
                if not (event.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)):
                    self.selected_cards.clear()
                    for card in self._cards:
                        card.set_selected(False)
                    self.update_preview()

            elif event.type() == QEvent.MouseMove and (event.buttons() & Qt.LeftButton):
                if hasattr(self, "_rubber_band") and self._rubber_band and self._rubber_band.isVisible():
                    rect = QRect(self._rubber_origin, event.pos()).normalized()
                    self._rubber_band.setGeometry(rect)
                    
                    for card in self._cards:
                        card_geo = QRect(card.mapTo(self.scroll.viewport(), QPoint(0, 0)), card.size())
                        card_obj = getattr(card, "path", getattr(card, "file_object", None))
                        if card_geo.intersects(rect):
                            if card_obj:
                                self.selected_cards.add(card_obj)
                                card.set_selected(True)
                        elif not (event.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)):
                            if card_obj and card_obj in self.selected_cards:
                                self.selected_cards.remove(card_obj)
                            card.set_selected(False)
                    self.update_preview()

            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                if hasattr(self, "_rubber_band") and self._rubber_band:
                    self._rubber_band.hide()
                self.update_preview()

        return super().eventFilter(obj, event)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.drop_lbl.isVisible():
            self.drop_lbl.resize(self.size())
        if self.view_mode == "grid":
            QTimer.singleShot(50, self._rebuild)
        if hasattr(self, "preview_panel") and self.preview_panel.isVisible():
            QTimer.singleShot(100, self.update_preview)

    def load_files(self, files):
        self.media_files = files
        self.selected_cards.clear()
        self._rebuild()

    def clear(self):
        self.media_files.clear()
        self.selected_cards.clear()
        self.count_lbl.setText("0 items")
        self.sel_lbl.setText("")
        for c in self._cards: c.deleteLater()
        self._cards.clear()
        self.table.setRowCount(0)

    def update_devices(self, devices, active_index=-1):
        if not hasattr(self, "device_cb"): return
        self.device_cb.blockSignals(True)
        self.device_cb.clear()
        if not devices:
            default_txt = "No Android device detected" if getattr(self, "mode", "") == "android" else "No iPhone detected"
            self.device_cb.addItem(default_txt)
        else:
            for dev in devices:
                if isinstance(dev, str):
                    self.device_cb.addItem(dev)
                else:
                    icon = "🤖 " if getattr(self, "mode", "") == "android" else "📱 "
                    self.device_cb.addItem(f"{icon}{dev.name()}", dev)
        if active_index >= 0:
            self.device_cb.setCurrentIndex(active_index)
        self.device_cb.blockSignals(False)

    def _toggle_preview_panel(self):
        show = self.preview_btn.isChecked()
        if show:
            self.preview_panel.show()
            self.content_splitter.setSizes([self.width() - 220, 220])
            self.update_preview()
        else:
            self.preview_panel.hide()

    def _on_splitter_moved(self, pos, index):
        self.update_preview()

    def _is_text_file(self, path):
        try:
            with open(path, "rb") as f:
                chunk = f.read(1024)
            if b"\x00" in chunk: return False
            chunk.decode('utf-8', errors='strict')
            return True
        except Exception: return False

    def update_preview(self):
        # Update CoverFlow if open
        mw = self.window()
        if mw and hasattr(mw, "coverflow_container") and mw.coverflow_container.isVisible():
            if hasattr(mw, "coverflow_widget"):
                files = self.get_coverflow_files()
                mw.coverflow_widget.set_files(files)

        self._current_preview_item = None
        if hasattr(self, "video_player"):
            self.video_player.stop_video()
            self.video_player.hide()

        if hasattr(self, "preview_gps_lbl"):
            self.preview_gps_lbl.hide()

        if not hasattr(self, "preview_panel") or not self.preview_panel.isVisible():
            return
            
        selected_paths_or_files = self.get_selected()
        if not selected_paths_or_files:
            self.preview_title.setText("Preview")
            self.preview_placeholder.setText("Select a file to preview")
            self.preview_placeholder.show()
            self.preview_image.hide()
            self.preview_text.hide()
            return
            
        first_item = selected_paths_or_files[0]
        
        if self.mode == "local":
            path = first_item
            if not os.path.exists(path) or os.path.isdir(path):
                self.preview_title.setText("Preview")
                self.preview_placeholder.setText("Select a file to preview")
                self.preview_placeholder.show()
                self.preview_image.hide()
                self.preview_text.hide()
                return
            
            name = os.path.basename(path)
            size_str = f" ({format_size(os.path.getsize(path))})" if os.path.exists(path) else ""
            self.preview_title.setText(f"{name}{size_str}")
            ext = os.path.splitext(name)[1].lower()
            
            if ext in VIDEO_EXTS:
                if HAS_QT_MULTIMEDIA and hasattr(self, "video_player"):
                    self.preview_placeholder.hide()
                    self.preview_image.hide()
                    self.preview_text.hide()
                    self.video_player.show()
                    self.video_player.load_video(path)
                else:
                    self.preview_placeholder.setText(f"Video file: {name}")
                    self.preview_placeholder.show()
                    self.preview_image.hide()
                    self.preview_text.hide()
                return
                
            image_extensions = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".tif", ".gif", ".bmp", ".webp"}
            text_extensions = {".txt", ".py", ".json", ".xml", ".html", ".css", ".js", ".sh", ".command", ".md", ".log", ".ini", ".cfg", ".yaml", ".yml", ".csv"}
            
            if ext in image_extensions:
                qimg = QImage()
                if ext in {".heic", ".heif"} and platform.system() == "Darwin":
                    tmp = os.path.join(tempfile.gettempdir(), f"_heic_pv_{os.getpid()}_{abs(hash(path))}.png")
                    ret = os.system(f'sips -s format png "{path}" --out "{tmp}" >/dev/null 2>&1')
                    if ret == 0 and os.path.exists(tmp):
                        reader = QImageReader(tmp)
                        reader.setAutoTransform(True)
                        qimg = reader.read()
                        try: os.unlink(tmp)
                        except Exception: pass
                else:
                    reader = QImageReader(path)
                    reader.setAutoTransform(True)
                    qimg = reader.read()

                if not qimg.isNull():
                    pix = QPixmap.fromImage(qimg)
                    dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
                    
                    max_w = max(100, int((self.preview_panel.width() - 16) * dpr))
                    max_h = max(100, int((self.preview_panel.height() - 120) * dpr))
                    
                    scaled_pix = pix.scaled(QSize(max_w, max_h), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    scaled_pix.setDevicePixelRatio(dpr)
                    self.preview_image.setPixmap(scaled_pix)
                    self.preview_image.setScaledContents(False)
                    self.preview_image.show()
                    self.preview_placeholder.hide()
                    self.preview_text.hide()

                    # Extract EXIF GPS metadata & reverse geocode location!
                    gps = extract_image_exif_gps(path)
                    if gps and hasattr(self, "preview_gps_lbl"):
                        loc_str = get_location_name_from_coords(gps[0], gps[1])
                        self.preview_gps_lbl.setText(f"📍 Location:\n{loc_str}\n({gps[0]:.4f}°, {gps[1]:.4f}°)")
                        self.preview_gps_lbl.show()
                    return
                else:
                    self.preview_placeholder.setText("Failed to load image preview")
                    self.preview_placeholder.show()
                    self.preview_image.hide()
                    self.preview_text.hide()
            elif ext in text_extensions or self._is_text_file(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(10000)
                    self.preview_text.setPlainText(content)
                    self.preview_text.show()
                    self.preview_placeholder.hide()
                    self.preview_image.hide()
                except Exception as e:
                    self.preview_placeholder.setText(f"Error reading text file:\n{e}")
                    self.preview_placeholder.show()
                    self.preview_image.hide()
                    self.preview_text.hide()
            else:
                self.preview_placeholder.setText("Preview not available for this file type")
                self.preview_placeholder.show()
                self.preview_image.hide()
                self.preview_text.hide()
        else:
            file_obj = first_item
            name = file_obj.name()
            size_str = f" ({format_size(file_obj.size)})" if hasattr(file_obj, "size") else ""
            self.preview_title.setText(f"{name}{size_str}")
            ext = os.path.splitext(name)[1].lower()
            
            if ext in VIDEO_EXTS:
                self.preview_placeholder.setText("Preview not supported for videos")
                self.preview_placeholder.show()
                self.preview_image.hide()
                self.preview_text.hide()
                return
                
            image_extensions = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".tif", ".gif", ".bmp", ".webp"}
            if ext in image_extensions:
                self._current_preview_item = file_obj
                def _on_preview_thumb(n, px):
                    if not shiboken or not shiboken.isValid(self):
                        return
                    if getattr(self, "_current_preview_item", None) != file_obj:
                        return
                    if not px.isNull() and self.preview_panel.isVisible():
                        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
                        max_w = max(100, int((self.preview_panel.width() - 16) * dpr))
                        max_h = max(100, int((self.preview_panel.height() - 120) * dpr))
                        scaled_pix = px.scaled(QSize(max_w, max_h), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        scaled_pix.setDevicePixelRatio(dpr)
                        self.preview_image.setPixmap(scaled_pix)
                        self.preview_image.setScaledContents(False)
                        self.preview_image.show()
                        self.preview_placeholder.hide()
                        self.preview_text.hide()
                get_iphone_thumb_async(file_obj, 1024, _on_preview_thumb)
            else:
                self.preview_placeholder.setText("Preview not available for iPhone non-image files")
                self.preview_placeholder.show()
                self.preview_image.hide()
                self.preview_text.hide()

# ── Marko Polo Movie & Fast Typewriter Speech Bubble ──────────────────────────
class RobotMovieLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setScaledContents(True)
        
        self.png_path = get_asset_path("markopolo.png")
        self.gif_path = get_asset_path("markopolo_animated.gif")
        if not os.path.exists(self.gif_path):
            self.gif_path = get_asset_path("robot_blink.gif")
        
        self.setStyleSheet("background: transparent;")
        
        self.static_pixmap = QPixmap(self.png_path) if os.path.exists(self.png_path) else QPixmap(36, 36)
        self.setPixmap(self.static_pixmap)
        
        if os.path.exists(self.gif_path):
            self.movie = QMovie(self.gif_path)
            self.movie.setScaledSize(QSize(36, 36))
        else:
            self.movie = None

    def start_animation(self):
        """Starts markopolo_animated.gif animation while text is typing."""
        if self.movie:
            if self.movie.state() != QMovie.Running:
                self.setMovie(self.movie)
                self.movie.start()

    def stop_animation(self):
        """Stops markopolo_animated.gif animation when text is done showing."""
        if self.movie and self.movie.state() == QMovie.Running:
            self.movie.stop()
            self.setPixmap(self.static_pixmap)

    def trigger_blink(self):
        self.start_animation()

    def stop_blink(self):
        self.stop_animation()

    def mousePressEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            mw = self.window()
            if mw and hasattr(mw, "_show_window_control_menu"):
                mw._show_window_control_menu(self.mapToGlobal(event.pos()))
                return True
        return super().mousePressEvent(event)


class SpeechBubbleCloud(QFrame):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setFixedWidth(310)
        self.setFixedHeight(32)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 2)
        
        self.full_text = text
        self.current_char_idx = 0
        
        self.label = QLabel("")
        layout.addWidget(self.label)
        
        # Fast Typewriter Timer for retro computer typing effect
        self.type_timer = QTimer(self)
        self.type_timer.setInterval(15) # 15ms per character = super fast typing!
        self.type_timer.timeout.connect(self._type_next_char)
        
        self.set_theme_mode(CURRENT_THEME_MODE)
        if text:
            self.setText(text)

    def set_theme_mode(self, mode):
        if mode == "dark":
            bg_color = "#1c1c1e"
            text_color = "#ffffff"
            border_color = "#ff453a"
            tooltip_bg = "#2c2c2e"
            tooltip_text = "#ffffff"
            tooltip_border = "#3a3a3c"
        else:
            bg_color = "#ffffff"
            text_color = "#111827"
            border_color = "#0a84ff"
            tooltip_bg = "#ffffff"
            tooltip_text = "#111827"
            tooltip_border = "#cbd5e1"
        
        self.label.setStyleSheet(f"QLabel {{ color: {text_color} !important; font-size: 11px; font-weight: 700; font-family: -apple-system, 'SF Mono', monospace; background: transparent; }}")
        self.setStyleSheet(f"""
            SpeechBubbleCloud {{
                background-color: {bg_color} !important;
                border: 1.5px solid {border_color};
                border-radius: 12px;
                border-bottom-left-radius: 2px;
            }}
            SpeechBubbleCloud QLabel {{
                color: {text_color} !important;
            }}
            QToolTip {{
                background-color: {tooltip_bg};
                color: {tooltip_text};
                border: 1px solid {tooltip_border};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }}
        """)

    def set_speech_text(self, text):
        self.setText(text)

    def setText(self, text):
        mw = self.window()
        if mw and hasattr(mw, "_robot_tips_enabled") and not mw._robot_tips_enabled:
            self.full_text = text
            self.label.setText("")
            return
        if self.full_text == text and self.label.text() == text:
            return
        self.full_text = text
        self.current_char_idx = 0
        self.label.setText("")
        
        # Start Marko Polo GIF animation on parent window
        if mw and hasattr(mw, "robot_widget") and mw.robot_widget and getattr(mw, "_robot_tips_enabled", True):
            mw.robot_widget.start_animation()
            
        self.type_timer.start()

    def _type_next_char(self):
        if self.current_char_idx < len(self.full_text):
            self.current_char_idx += 1
            self.label.setText(self.full_text[:self.current_char_idx])
        else:
            self.type_timer.stop()
            # Stop Marko Polo GIF animation when text is done showing!
            mw = self.window()
            if mw and hasattr(mw, "robot_widget") and mw.robot_widget:
                mw.robot_widget.stop_animation()

    def text(self):
        return self.full_text


# ── Circular Transfer Progress Ring Widget ─────────────────────────────────────
class CircularTransferProgress(QWidget):
    """Custom circular progress bar for file transfer visualization in the middle panel.
    Shows a donut-style ring that fills as files transfer, with size info in the center."""

    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0  # 0.0 to 1.0
        self._active = False
        self._paused = False
        self._transferred_bytes = 0
        self._total_bytes = 0
        self._file_count = 0
        self._total_files = 0
        self._theme_mode = CURRENT_THEME_MODE

        self.setFixedSize(112, 112)

        # Glow animation timer (runs continuously for smooth ambient aura)
        self._glow_phase = 0.0
        self._glow_timer = QTimer(self)
        self._glow_timer.setInterval(30)
        self._glow_timer.timeout.connect(self._animate_glow)
        self._glow_timer.start()

    def set_theme_mode(self, mode):
        self._theme_mode = mode
        self.update()

    def set_progress(self, value):
        """Set progress 0.0 to 1.0"""
        self._progress = max(0.0, min(1.0, value))
        if value > 0:
            self._active = True
        self.update()

    def set_active(self, active):
        self._active = active
        self._paused = False
        self.update()

    def set_paused(self, paused):
        self._paused = paused
        self.update()

    def set_transfer_info(self, transferred_bytes, total_bytes, file_count, total_files):
        self._transferred_bytes = transferred_bytes
        self._total_bytes = total_bytes
        self._file_count = file_count
        self._total_files = total_files

        byte_pct = (transferred_bytes / total_bytes) if (total_bytes > 0 and transferred_bytes > 0) else 0.0
        file_pct = (file_count / total_files) if total_files > 0 else 0.0

        self._progress = min(1.0, max(0.0, max(byte_pct, file_pct)))
        if file_count > 0 or transferred_bytes > 0 or self._progress > 0:
            self._active = True
        self.update()

    def reset(self):
        self._progress = 0.0
        self._active = False
        self._paused = False
        self._transferred_bytes = 0
        self._total_bytes = 0
        self._file_count = 0
        self._total_files = 0
        self._glow_phase = 0.0
        self.update()

    def _animate_glow(self):
        import math
        # Smooth breathing pulse (~3.5 second cycle)
        self._glow_phase = (self._glow_phase + 0.04) % (2 * math.pi)
        self.update()

    @staticmethod
    def _format_size(size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f}GB"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx, cy = w // 2, h // 2
        radius = min(w, h) // 2 - 10
        ring_width = 9

        is_dark = self._theme_mode == "dark"
        rect = QRect(cx - radius, cy - radius, radius * 2, radius * 2)

        import math
        pulse_val = (math.sin(self._glow_phase) + 1.0) / 2.0  # 0.0 to 1.0 breathing wave

        # ── 1. Outer Neon Breathing Aura (Matching #0a84ff button blue) ──
        if self._active and not self._paused:
            glow_alpha_outer = int(30 + 45 * pulse_val)
            glow_pen_outer = QPen(QColor(10, 132, 255, glow_alpha_outer), ring_width + 8, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(glow_pen_outer)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(rect)

            glow_alpha_inner = int(55 + 65 * pulse_val)
            glow_pen_inner = QPen(QColor(10, 132, 255, glow_alpha_inner), ring_width + 4, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(glow_pen_inner)
            painter.drawEllipse(rect)
        elif not self._active:
            idle_alpha = int(12 + 18 * pulse_val)
            idle_aura = QPen(QColor(10, 132, 255, idle_alpha), ring_width + 4, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(idle_aura)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(rect)

        # ── 2. Glass Center Disc ──
        glass_radius = radius - ring_width // 2 - 2
        glass_rect = QRect(cx - glass_radius, cy - glass_radius, glass_radius * 2, glass_radius * 2)
        glass_bg = QColor(10, 12, 22, 200) if is_dark else QColor(255, 255, 255, 230)
        glass_border = QColor(10, 132, 255, 55) if (is_dark and self._active) else QColor(0, 0, 0, 15)
        painter.setPen(QPen(glass_border, 1.2))
        painter.setBrush(QBrush(glass_bg))
        painter.drawEllipse(glass_rect)

        # ── 3. Background Track Ring ──
        track_color = QColor("#1c1c30") if is_dark else QColor("#e2e8f0")
        pen = QPen(track_color, ring_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect)

        # ── 4. Dynamic Progress Arc ──
        pct = int(self._progress * 100) if (self._active or self._progress > 0) else 0
        pct_text = f"{pct}%"

        if (self._active or self._progress > 0) and self._progress > 0:
            if self._paused:
                arc_color = QColor("#ff9f0a")  # Vibrant orange when paused
            else:
                arc_color = QColor("#0a84ff")  # Same electric blue as Source/Local button backgrounds

            arc_pen = QPen(arc_color, ring_width, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(arc_pen)
            start_angle = 90 * 16  # 12 o'clock
            span_angle = int(-self._progress * 360 * 16)
            painter.drawArc(rect, start_angle, span_angle)

        # ── 5. Center Typography (Bolder & Bigger) ──
        pct_font = QFont("SF Mono, Menlo, Consolas, monospace", 19, QFont.Black)
        painter.setFont(pct_font)

        if self._active and self._paused:
            pct_color = QColor("#ff9f0a")
        elif self._active:
            pct_color = QColor("#0a84ff") if is_dark else QColor("#0066cc")
        else:
            pct_color = QColor("#64748b") if is_dark else QColor("#94a3b8")

        painter.setPen(pct_color)
        painter.drawText(rect, Qt.AlignHCenter | Qt.AlignVCenter, pct_text)

        # Subtext below percentage
        if self._active and self._total_bytes > 0:
            sub_text = f"{self._format_size(self._transferred_bytes)} / {self._format_size(self._total_bytes)}"
        elif self._active and self._total_files > 0:
            sub_text = f"{self._file_count} / {self._total_files} files"
        else:
            sub_text = "Ready"

        sub_font = QFont("SF Mono, Menlo, Consolas, monospace", 7, QFont.Bold)
        painter.setFont(sub_font)
        painter.setPen(QColor("#94a3b8") if is_dark else QColor("#64748b"))
        sub_rect = QRect(cx - radius, cy + 13, radius * 2, 18)
        painter.drawText(sub_rect, Qt.AlignHCenter | Qt.AlignTop, sub_text)

        # File count above percentage when active
        if self._active and self._total_files > 0:
            count_text = f"{self._file_count}/{self._total_files} files"
            count_font = QFont("SF Mono, Menlo, Consolas, monospace", 7, QFont.Bold)
            painter.setFont(count_font)
            painter.setPen(QColor("#94a3b8") if is_dark else QColor("#64748b"))
            count_rect = QRect(cx - radius, cy - 27, radius * 2, 16)
            painter.drawText(count_rect, Qt.AlignHCenter | Qt.AlignBottom, count_text)

        # Paused indicator
        if self._active and self._paused:
            pause_font = QFont("SF Mono, Menlo, Consolas, monospace", 7, QFont.Bold)
            painter.setFont(pause_font)
            painter.setPen(QColor("#ff9f0a"))
            pause_rect = QRect(cx - radius, cy + 25, radius * 2, 16)
            painter.drawText(pause_rect, Qt.AlignHCenter | Qt.AlignTop, "PAUSED")

        painter.end()


class TransferControlButtons(QWidget):
    """Pause / Continue / Stop buttons for file transfer control."""

    pause_clicked = Signal()
    continue_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme_mode = CURRENT_THEME_MODE

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setFixedSize(36, 28)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.setToolTip("Pause the current file transfer")
        self.pause_btn.clicked.connect(self.pause_clicked.emit)

        self.continue_btn = QPushButton("▶")
        self.continue_btn.setFixedSize(36, 28)
        self.continue_btn.setCursor(Qt.PointingHandCursor)
        self.continue_btn.setToolTip("Continue the paused file transfer")
        self.continue_btn.clicked.connect(self.continue_clicked.emit)
        self.continue_btn.setEnabled(False)

        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setFixedSize(36, 28)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setToolTip("Stop and cancel the current file transfer")
        self.stop_btn.clicked.connect(self.stop_clicked.emit)

        layout.addStretch()
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.continue_btn)
        layout.addWidget(self.stop_btn)
        layout.addStretch()

        self.set_active(False)

    def set_theme_mode(self, mode):
        self._theme_mode = mode
        self._apply_style()

    def set_active(self, active):
        self.setVisible(active)
        if active:
            self._apply_style()

    def set_paused(self, paused):
        self.pause_btn.setEnabled(not paused)
        self.continue_btn.setEnabled(paused)
        self._apply_style()

    def _apply_style(self):
        is_dark = self._theme_mode == "dark"
        bg = "rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.04)"
        border = "rgba(255,255,255,0.12)" if is_dark else "rgba(0,0,0,0.1)"
        text = "#ffffff" if is_dark else "#111827"
        hover_bg = "rgba(10,132,255,0.3)" if is_dark else "rgba(10,132,255,0.15)"
        disabled_text = "rgba(255,255,255,0.2)" if is_dark else "rgba(0,0,0,0.2)"
        stop_hover = "rgba(255,69,58,0.3)" if is_dark else "rgba(255,69,58,0.15)"

        base_style = f"""
            QPushButton {{
                background: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {hover_bg};
                border-color: #0a84ff;
            }}
            QPushButton:disabled {{
                color: {disabled_text};
                background: transparent;
                border-color: transparent;
            }}
        """

        stop_style = f"""
            QPushButton {{
                background: {bg};
                color: #ff453a;
                border: 1px solid {border};
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {stop_hover};
                border-color: #ff453a;
            }}
            QPushButton:disabled {{
                color: {disabled_text};
                background: transparent;
                border-color: transparent;
            }}
        """

        self.pause_btn.setStyleSheet(base_style)
        self.continue_btn.setStyleSheet(base_style)
        self.stop_btn.setStyleSheet(stop_style)


# ── Draggable Gray Sign for Resizing/Pushing Middle Panel ──────────────────────
class MovePanelSign(QLabel):
    def __init__(self, parent=None):
        super().__init__("<- move panel ->", parent)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.SizeHorCursor)
        self.setFixedHeight(24)
        self.setToolTip("Click and drag left or right to move middle panel position")
        self.set_theme_mode(CURRENT_THEME_MODE)
        self._drag_start_x = 0
        self._initial_sizes = []

    def set_theme_mode(self, mode):
        color = "rgba(255, 255, 255, 0.35)" if mode == "dark" else "rgba(0, 0, 0, 0.35)"
        self.setStyleSheet(f"""
            MovePanelSign {{
                background: transparent;
                color: {color};
                border: none;
                font-size: 10px;
                font-weight: 500;
                font-family: -apple-system, sans-serif;
            }}
            MovePanelSign:hover {{
                color: #3b82f6;
            }}
        """)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start_x = e.globalPosition().x() if hasattr(e, "globalPosition") else e.globalPos().x()
            mw = self.window()
            if mw and hasattr(mw, "splitter"):
                self._initial_sizes = mw.splitter.sizes()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if (e.buttons() & Qt.LeftButton) and self._initial_sizes and len(self._initial_sizes) == 3:
            curr_x = e.globalPosition().x() if hasattr(e, "globalPosition") else e.globalPos().x()
            delta_x = int(curr_x - self._drag_start_x)
            
            mw = self.window()
            if mw and hasattr(mw, "splitter"):
                s0 = max(100, int(self._initial_sizes[0] + delta_x))
                s1 = self._initial_sizes[1]
                s2 = max(100, int(self._initial_sizes[2] - delta_x))
                mw.splitter.setSizes([s0, s1, s2])
                # Store as user's preferred position so resizes preserve it
                if hasattr(mw, "_user_splitter_sizes"):
                    mw._user_splitter_sizes = [s0, s1, s2]
        super().mouseMoveEvent(e)

# ── Update Check Popup Dialog ──────────────────────────────────────────────────
class UpdateCheckDialog(QDialog):
    """
    Sleek Dark Popup Modal Window that connects to server and lets user check or download updates.
    """
    def __init__(self, current_version=__version__, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.update_info = None

        self.setWindowTitle("Update Check - Marko Polo Explorer")
        self.setFixedSize(500, 260)
        self.setStyleSheet("""
            QDialog { background-color: #1c1c1e; color: #ffffff; }
            QLabel { color: #f0f0f0; }
            QPushButton {
                background: #2c2c2e; color: #ffffff; border: 1px solid #3a3a3c;
                border-radius: 6px; padding: 7px 16px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: #0a84ff; border-color: #0a84ff; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        self.status_title = QLabel("Checking Server Version...")
        self.status_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0a84ff;")

        self.details_lbl = QLabel("Connecting to server (http://marko.com.hr/markopolo/version.json)...")
        self.details_lbl.setWordWrap(True)
        self.details_lbl.setStyleSheet("font-size: 12px; color: #8e8e93;")

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 0)
        self.pbar.setFixedHeight(6)
        self.pbar.setStyleSheet("""
            QProgressBar { background: #2c2c2e; border-radius: 3px; border: none; }
            QProgressBar::chunk { background: #0a84ff; border-radius: 3px; }
        """)

        self.btn_box = QHBoxLayout()
        self.btn_box.setSpacing(10)
        self.btn_box.addStretch(1)

        self.close_btn = QPushButton("Cancel")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)
        self.btn_box.addWidget(self.close_btn)

        layout.addWidget(self.status_title)
        layout.addWidget(self.details_lbl)
        layout.addWidget(self.pbar)
        layout.addStretch(1)
        layout.addLayout(self.btn_box)

        # Start background update check thread
        self.thread = CheckUpdateThread(current_version=self.current_version)
        self.thread.update_found.connect(self._on_update_found)
        self.thread.no_update.connect(self._on_no_update)
        self.thread.check_failed.connect(self._on_check_failed)
        self.thread.start()

    def _on_update_found(self, data):
        self.update_info = data
        version_str = data.get("version", "newer")
        notes = data.get("release_notes", "Performance & stability improvements.")

        self.pbar.hide()
        self.status_title.setText(f"🚀 Update Available: v{version_str}")
        self.status_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #30d158;")

        self.details_lbl.setText(
            f"Installed Version: v{self.current_version}\n"
            f"Latest Version on Server: v{version_str}\n\n"
            f"Release Notes:\n{notes}"
        )

        # Standalone Windows .exe builds can't self-update from the Python zip:
        # send those users to the website to grab the latest exe instead.
        is_frozen_windows_exe = (
            (getattr(sys, "frozen", False) or "__compiled__" in dir())
            and sys.platform == "win32"
        )

        if is_frozen_windows_exe:
            self.install_btn = QPushButton("🌐 Download Latest from Website")
            self.install_btn.clicked.connect(self._open_download_website)
        else:
            self.install_btn = QPushButton("📥 Download & Install Update")
            self.install_btn.clicked.connect(self.accept)

        self.install_btn.setCursor(Qt.PointingHandCursor)
        self.install_btn.setStyleSheet("""
            QPushButton {
                background: #30d158; color: white; border: 1px solid #30d158;
                border-radius: 6px; padding: 7px 16px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: #28b84c; border-color: #28b84c; }
        """)

        self.close_btn.setText("Later")
        self.btn_box.insertWidget(0, self.install_btn)

    def _open_download_website(self):
        import webbrowser
        webbrowser.open("http://marko.com.hr/markopolo/")
        self.reject()

    def _on_no_update(self):
        self.pbar.hide()
        self.status_title.setText("✅ You Have the Latest Version")
        self.status_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #30d158;")
        self.details_lbl.setText(f"Marko Polo Explorer v{self.current_version} is currently up to date.")
        self.close_btn.setText("OK")

    def _on_check_failed(self, err):
        self.pbar.hide()
        self.status_title.setText("⚠️ Update Check Failed")
        self.status_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ff9500;")
        self.details_lbl.setText(f"Could not connect to update server:\n{err}")
        self.close_btn.setText("Close")


# ── iOS-Style Toggle Switch Widget ────────────────────────────────────────────
class ToggleSwitch(QWidget):
    """An iOS-style animated toggle switch widget."""
    toggled = Signal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._knob_pos = 1.0 if not checked else 21.0
        self.setFixedSize(46, 26)
        self.setCursor(Qt.PointingHandCursor)

        self._animation = QPropertyAnimation(self, b"knob_position")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)

    def _get_knob_pos(self):
        return self._knob_pos

    def _set_knob_pos(self, val):
        self._knob_pos = val
        self.update()

    knob_position = Property(float, _get_knob_pos, _set_knob_pos)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked, animate=True):
        if self._checked == checked:
            return
        self._checked = checked
        target = 21.0 if checked else 1.0
        if animate:
            self._animation.stop()
            self._animation.setStartValue(self._knob_pos)
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self._knob_pos = target
            self.update()

    def mousePressEvent(self, e):
        self._checked = not self._checked
        target = 21.0 if self._checked else 1.0
        self._animation.stop()
        self._animation.setStartValue(self._knob_pos)
        self._animation.setEndValue(target)
        self._animation.start()
        self.toggled.emit(self._checked)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Track
        if self._checked:
            track_color = QColor("#30d158")  # Green when on
        else:
            if CURRENT_THEME_MODE == "dark":
                track_color = QColor(120, 120, 128, 90)
            else:
                track_color = QColor(200, 200, 204)

        p.setBrush(QBrush(track_color))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, 46, 26, 13, 13)

        # Knob
        p.setBrush(QBrush(QColor("#ffffff")))
        p.setPen(QPen(QColor(0, 0, 0, 25), 0.5))
        knob_x = self._knob_pos
        p.drawEllipse(int(knob_x), 1, 24, 24)
        p.end()


# ── Special Commands Confirmation Dialog ─────────────────────────────────────
class SpecialCommandsConfirmDialog(QDialog):
    """Custom confirmation dialog for Special Commands with explicit Yes and No buttons."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ Special Commands")
        self.setFixedWidth(460)
        self.setMinimumHeight(260)
        self.setModal(True)

        is_dark = (CURRENT_THEME_MODE == "dark")
        bg_color = "#1e1e1e" if is_dark else "#ffffff"
        text_color = "#ffffff" if is_dark else "#111111"
        subtext_color = "#aaaaaa" if is_dark else "#555555"
        border_color = "#333333" if is_dark else "#d0d0d0"
        btn_bg = "#2a2a2a" if is_dark else "#eeeeee"
        btn_hover = "#3a3a3a" if is_dark else "#dddddd"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 24)
        lay.setSpacing(18)

        # Top area: Emoji icon + Title + Subtitle
        top_lay = QHBoxLayout()
        top_lay.setSpacing(16)
        top_lay.setAlignment(Qt.AlignTop)

        icon_lbl = QLabel("⚠️")
        icon_lbl.setStyleSheet("font-size: 38px; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        top_lay.addWidget(icon_lbl)

        text_lay = QVBoxLayout()
        text_lay.setSpacing(8)

        q_lbl = QLabel("Are you sure you know what you're doing?")
        q_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {text_color}; background: transparent;")
        q_lbl.setWordWrap(True)
        text_lay.addWidget(q_lbl)

        info_lbl = QLabel(
            "Special Commands include tools like deleting duplicate files, "
            "auto-organizing into folders, and extracting file types.\n\n"
            "These actions can modify or delete files permanently."
        )
        info_lbl.setStyleSheet(f"font-size: 12px; font-weight: 400; color: {subtext_color}; background: transparent;")
        info_lbl.setWordWrap(True)
        text_lay.addWidget(info_lbl)

        top_lay.addLayout(text_lay, 1)
        lay.addLayout(top_lay)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {border_color};")
        lay.addWidget(div)

        # Bottom buttons: No (Reject) and Yes (Accept)
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(12)
        btn_lay.addStretch(1)

        self.no_btn = QPushButton("No")
        self.no_btn.setCursor(Qt.PointingHandCursor)
        self.no_btn.setFixedSize(110, 38)
        self.no_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
        """)
        self.no_btn.clicked.connect(self.reject)
        btn_lay.addWidget(self.no_btn)

        self.yes_btn = QPushButton("Yes")
        self.yes_btn.setCursor(Qt.PointingHandCursor)
        self.yes_btn.setFixedSize(110, 38)
        self.yes_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #30d158;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #28c04e;
            }}
        """)
        self.yes_btn.clicked.connect(self.accept)
        btn_lay.addWidget(self.yes_btn)

        lay.addLayout(btn_lay)


# ── Settings Dialog ───────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    """Settings window with About info and iOS-style toggleable options."""

    # Signals emitted when settings change
    theme_changed = Signal(str)       # "dark" or "light"
    special_commands_changed = Signal(bool)
    gjuro_mode_changed = Signal(bool)
    sound_effects_changed = Signal(bool)
    robot_tips_changed = Signal(bool)
    compact_mode_changed = Signal(bool)
    auto_refresh_changed = Signal(bool)

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self.setMaximumWidth(560)
        self.setMinimumHeight(680)
        self.resize(500, 720)
        self.setModal(True)
        self._settings = settings or {}
        self._toggles = {}
        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header with app icon and title ──
        header = QFrame()
        header_lay = QVBoxLayout(header)
        header_lay.setContentsMargins(24, 24, 24, 16)
        header_lay.setSpacing(8)
        header_lay.setAlignment(Qt.AlignCenter)

        # App icon
        icon_label = QLabel()
        icon_path = get_asset_path("markopolo.png")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pix)
        icon_label.setAlignment(Qt.AlignCenter)
        header_lay.addWidget(icon_label)

        title = QLabel("Marko Polo Explorer")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 700; padding: 0; margin: 0;")
        header_lay.addWidget(title)
        self._title_label = title

        # Version and Update button in a horizontal layout
        ver_lay = QHBoxLayout()
        ver_lay.setSpacing(10)
        ver_lay.setAlignment(Qt.AlignCenter)

        ver = QLabel(f"Version {__version__}")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("font-size: 12px; font-weight: 500; padding: 0; margin: 0;")
        ver_lay.addWidget(ver)
        self._ver_label = ver

        update_btn = QPushButton("🔄 Check for Updates")
        update_btn.setCursor(Qt.PointingHandCursor)
        update_btn.setToolTip("Check server for Marko Polo Explorer updates")
        update_btn.clicked.connect(self._check_updates)
        ver_lay.addWidget(update_btn)
        self._update_btn = update_btn

        header_lay.addLayout(ver_lay)

        layout.addWidget(header)
        self._header = header

        # ── Divider ──
        divider = QFrame()
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        self._divider = divider

        # ── Settings rows ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(16, 12, 16, 16)
        content_lay.setSpacing(4)

        settings_items = [
            ("dark_mode", "🌙", "Dark Mode", "Switch between dark and light themes"),
            ("show_special_commands", "✨", "Show Special Commands", "Show the Special Commands button in the middle panel"),
            ("sound_effects", "🔊", "Sound Effects", "Play UI sound effects for actions"),
            ("robot_tips", "💬", "Robot Tips", "Show Marko Polo assistant & speech bubble tips in toolbar"),
            ("compact_mode", "📐", "Compact Mode", "Reduce padding and spacing for smaller screens"),
            ("auto_refresh", "🔄", "Auto-Refresh", "Automatically refresh panels when files change"),
            ("gjuro_mode", "🎮", "Djuro Mode", "Browse with WASD: W/S = Up/Down, D or Enter = Open/Preview, A = Back"),
        ]

        for key, emoji, label, desc in settings_items:
            row = self._make_toggle_row(key, emoji, label, desc)
            content_lay.addWidget(row)

        # Report a bug link row
        bug_row = self._make_link_row(
            "🐛",
            "Report a Bug",
            "Send feedback or report an issue at marko.com.hr/markopolo/#contact",
            "https://www.marko.com.hr/markopolo/#contact"
        )
        content_lay.addWidget(bug_row)

        content_lay.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self._scroll = scroll
        self._content = content

        # ── Footer ──
        footer = QFrame()
        footer_lay = QHBoxLayout(footer)
        footer_lay.setContentsMargins(16, 12, 16, 16)

        footer_text = QLabel("Built with ❤️ by Marko")
        footer_text.setStyleSheet("font-size: 10px; font-weight: 400;")
        footer_lay.addWidget(footer_text)
        self._footer_text = footer_text

        footer_lay.addStretch()

        close_btn = QPushButton("Done")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.accept)
        footer_lay.addWidget(close_btn)
        self._close_btn = close_btn

        layout.addWidget(footer)
        self._footer = footer

    def _check_updates(self):
        """Open update check dialog."""
        main_win = self.parent()
        if main_win and hasattr(main_win, "_open_update_popup_dialog"):
            main_win._open_update_popup_dialog()
        else:
            dlg = UpdateCheckDialog(current_version=__version__, parent=self)
            dlg.exec()

    def _make_toggle_row(self, key, emoji, label, desc):
        """Create a single settings toggle row with adequate height for two rows of text."""
        row = QFrame()
        row.setMinimumHeight(68)
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(14, 10, 14, 10)
        row_lay.setSpacing(12)

        # Emoji icon
        emoji_lbl = QLabel(emoji)
        emoji_lbl.setFixedWidth(30)
        emoji_lbl.setStyleSheet("font-size: 20px;")
        emoji_lbl.setAlignment(Qt.AlignCenter)
        row_lay.addWidget(emoji_lbl)

        # Label + description
        text_lay = QVBoxLayout()
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(3)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        text_lay.addWidget(name_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("font-size: 11px; font-weight: 400;")
        desc_lbl.setWordWrap(True)
        text_lay.addWidget(desc_lbl)

        row_lay.addLayout(text_lay, 1)

        # Toggle switch
        toggle = ToggleSwitch(checked=self._settings.get(key, False))
        toggle.toggled.connect(lambda checked, k=key: self._on_toggle(k, checked))
        row_lay.addWidget(toggle)

        self._toggles[key] = toggle
        row._name_lbl = name_lbl
        row._desc_lbl = desc_lbl
        row._emoji_lbl = emoji_lbl

        if key == "gjuro_mode":
            instructions = (
                "🎮 Djuro Mode Controls:\n"
                "• W: Move UP 1 file/item\n"
                "• S: Move DOWN 1 file/item\n"
                "• D or Enter: Open highlighted folder or preview .jpg/image file\n"
                "• A: Move back in folder history\n"
                "Works seamlessly in both Grid and List modes!"
            )
            row.setToolTip(instructions)
            name_lbl.setToolTip(instructions)
            desc_lbl.setToolTip(instructions)

        return row

    def _make_link_row(self, emoji, label, desc, url):
        """Create a clickable link row that opens an external URL."""
        row = QFrame()
        row.setMinimumHeight(68)
        row.setCursor(Qt.PointingHandCursor)
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(14, 10, 14, 10)
        row_lay.setSpacing(12)

        # Emoji icon
        emoji_lbl = QLabel(emoji)
        emoji_lbl.setFixedWidth(30)
        emoji_lbl.setStyleSheet("font-size: 20px;")
        emoji_lbl.setAlignment(Qt.AlignCenter)
        row_lay.addWidget(emoji_lbl)

        # Label + description
        text_lay = QVBoxLayout()
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(3)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        text_lay.addWidget(name_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("font-size: 11px; font-weight: 400;")
        desc_lbl.setWordWrap(True)
        text_lay.addWidget(desc_lbl)

        row_lay.addLayout(text_lay, 1)

        # Action button
        btn = QPushButton("Open ↗")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        row_lay.addWidget(btn)

        row.mousePressEvent = lambda e: QDesktopServices.openUrl(QUrl(url))
        row._name_lbl = name_lbl
        row._desc_lbl = desc_lbl
        row._emoji_lbl = emoji_lbl
        row._action_btn = btn
        return row

    def _on_toggle(self, key, checked):
        """Handle toggle changes with optional confirmation dialogs."""
        if key == "show_special_commands" and checked:
            confirm = SpecialCommandsConfirmDialog(parent=self)
            if confirm.exec() != QDialog.Accepted:
                # User selected No -> keep hidden & revert toggle
                self._toggles[key].setChecked(False)
                self._settings[key] = False
                self.special_commands_changed.emit(False)
                return
            # User selected Yes -> turn on
            self._settings[key] = True
            self.special_commands_changed.emit(True)
            return
        elif key == "show_special_commands" and not checked:
            self._settings[key] = False
            self.special_commands_changed.emit(False)
            return
        elif key == "gjuro_mode":
            self.gjuro_mode_changed.emit(checked)
        elif key == "dark_mode":
            new_mode = "dark" if checked else "light"
            self.theme_changed.emit(new_mode)
        elif key == "sound_effects":
            self.sound_effects_changed.emit(checked)
        elif key == "robot_tips":
            self.robot_tips_changed.emit(checked)
        elif key == "compact_mode":
            self.compact_mode_changed.emit(checked)
        elif key == "auto_refresh":
            self.auto_refresh_changed.emit(checked)

        self._settings[key] = checked

    def get_settings(self):
        """Return current settings dictionary."""
        return dict(self._settings)

    def _apply_theme(self):
        """Apply theme-aware styling to the entire dialog."""
        is_dark = (CURRENT_THEME_MODE == "dark")
        bg = "#1e1e1e" if is_dark else "#f9fafb"
        header_bg = "#18181a" if is_dark else "#f3f4f6"
        row_bg = "#27272a" if is_dark else "#ffffff"
        row_hover = "#323238" if is_dark else "#f1f5f9"
        text_color = "#ffffff" if is_dark else "#111827"
        subtext = "#a1a1aa" if is_dark else "#4b5563"
        border = "#3f3f46" if is_dark else "#e5e7eb"
        accent = "#0a84ff"
        tooltip_bg = "#2c2c2e" if is_dark else "#ffffff"
        tooltip_text = "#ffffff" if is_dark else "#111827"
        tooltip_border = "#444446" if is_dark else "#cbd5e1"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {text_color};
            }}
            QLabel {{
                color: {text_color};
            }}
            QToolTip {{
                background-color: {tooltip_bg};
                color: {tooltip_text};
                border: 1px solid {tooltip_border};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
        """)

        self._header.setStyleSheet(f"""
            QFrame {{
                background: {header_bg};
                border: none;
                border-bottom: none;
            }}
        """)
        self._title_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {text_color}; padding: 0; margin: 0; background: transparent;")
        self._ver_label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {subtext}; padding: 0; margin: 0; background: transparent;")

        if hasattr(self, "_update_btn") and self._update_btn:
            self._update_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BTN_BG};
                    color: {text_color};
                    border: 1px solid {border};
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {BTN_HOVER};
                    color: {accent};
                    border-color: {accent};
                }}
            """)

        self._divider.setStyleSheet(f"background: {border};")

        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {bg};
                border: none;
            }}
        """)
        self._content.setStyleSheet(f"background: {bg};")

        # Style toggle and link rows
        for child in self._content.findChildren(QFrame):
            if hasattr(child, "_name_lbl"):
                child.setStyleSheet(f"""
                    QFrame {{
                        background: {row_bg};
                        border: 1px solid {border};
                        border-radius: 10px;
                        margin: 2px 0px;
                    }}
                    QFrame:hover {{
                        background: {row_hover};
                    }}
                """)
                child._name_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {text_color} !important; border: none; background: transparent;")
                child._desc_lbl.setStyleSheet(f"font-size: 11px; font-weight: 400; color: {subtext} !important; border: none; background: transparent;")
                child._emoji_lbl.setStyleSheet(f"font-size: 20px; border: none; background: transparent;")
                if hasattr(child, "_action_btn"):
                    child._action_btn.setStyleSheet(f"""
                        QPushButton {{
                            background: {BTN_BG};
                            color: {accent};
                            border: 1px solid {border};
                            border-radius: 6px;
                            padding: 6px 12px;
                            font-size: 11px;
                            font-weight: 600;
                        }}
                        QPushButton:hover {{
                            background: {accent};
                            color: white;
                            border-color: {accent};
                        }}
                    """)

        self._footer.setStyleSheet(f"""
            QFrame {{
                background: {header_bg};
                border-top: 1px solid {border};
            }}
        """)
        self._footer_text.setStyleSheet(f"font-size: 10px; font-weight: 400; color: {subtext}; border: none; background: transparent;")
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {accent};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {ACCENT2};
            }}
        """)


# ── Main Window (ImageCaptureClone) ───────────────────────────────────────────
class ImageCaptureClone(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Marko Polo Explorer v{__version__}")
        self.resize(1280, 780)
        self._center_on_screen()
        
        ico_path = os.path.join(script_dir, "markopolo.ico")
        png_path = os.path.join(script_dir, "markopolo.png")
        icon_path = ico_path if (sys.platform == "win32" and os.path.exists(ico_path)) else png_path
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.manager = None
        self.current_camera = None
        self.active_devices = []
        self.download_queue = []
        self.downloading_now = False
        self.magic_mode_active = False
        self.extract_png_active = False
        self.overwrite_policy = "ask"
        self.transfer_paused = False
        self.transfer_total_bytes = 0
        self.transfer_done_bytes = 0
        
        self.active_panel = "left"
        self.demo_mode = False
        self.simulated_files = []

        # Install global application event filter for instant WASD / Space / Shortcut handling
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
        
        # Pulse timer for header glow animation
        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(50)
        self.pulse_timer.timeout.connect(self._update_pulse_glow)
        self.pulse_alpha = 0
        self.pulse_direction = 1
        
        # Debounce timer for resizing grid icons dynamically
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(120)
        self.resize_timer.timeout.connect(self._apply_thumb_resize)
        
        self._setup_style()
        self._build_ui()
        
        # Inactivity Idle Timer ("...bored? lol 🤖")
        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.setInterval(7000)
        self.idle_timer.timeout.connect(self._on_user_idle)
        self.idle_timer.start()

        # Defer device scanning and session restore to make window launch INSTANTLY!
        QTimer.singleShot(10, self._init_manager)
        QTimer.singleShot(20, self._restore_session)
        QTimer.singleShot(50, self._update_splitter_sizes)
        QTimer.singleShot(3000, lambda: self._check_for_updates(silent=True))

    def _center_on_screen(self):
        """Center window on primary screen, keeping titlebar safely in bounds."""
        try:
            screen = QGuiApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                w = min(1280, geo.width() - 40)
                h = min(780, geo.height() - 60)
                self.resize(w, h)
                x = geo.x() + (geo.width() - w) // 2
                y = geo.y() + (geo.height() - h) // 2
                y = max(geo.y() + 35, y)
                self.move(x, y)
        except Exception as ex:
            print(f"Centering error: {ex}")

    def _toggle_fullscreen(self):
        if self.isMaximized() or self.isFullScreen():
            self.showNormal()
            if hasattr(self, "max_btn"):
                self.max_btn.setText("⛶ Fullscreen")
        else:
            self.showMaximized()
            if hasattr(self, "max_btn"):
                self.max_btn.setText("🗗 Restore")

    def _show_window_control_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background-color: {PANEL_BG}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; border-radius: 6px; }}
            QMenu::item {{ padding: 6px 18px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
            QMenu::item:selected {{ background-color: {ACCENT}; color: #ffffff; }}
        """)

        reset_act = QAction("🎯 Reset Window to Center (1280x780)", self)
        full_act = QAction("🗗 Restore Window" if (self.isMaximized() or self.isFullScreen()) else "⛶ Fullscreen / Maximize", self)
        min_act = QAction("🗕 Minimize Window", self)

        menu.addAction(reset_act)
        menu.addAction(full_act)
        menu.addSeparator()
        menu.addAction(min_act)

        act = menu.exec(global_pos)
        if act == reset_act:
            if self.isMaximized() or self.isFullScreen():
                self.showNormal()
            self._center_on_screen()
        elif act == full_act:
            self._toggle_fullscreen()
        elif act == min_act:
            self.showMinimized()

    def register_button_alt_text(self, btn, text):
        if not btn: return
        btn.setToolTip(text)
        btn.setProperty("robot_alt_text", text)
        btn.installEventFilter(self)

    def reset_idle_timer(self):
        if hasattr(self, "idle_timer"):
            self.idle_timer.start(7000)

    def _on_user_idle(self):
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.setText("…bored? lol 🤖")
        if hasattr(self, "robot_widget"):
            self.robot_widget.trigger_blink()

    def _setup_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background:{BG}; }}
            QSplitter::handle:horizontal {{
                background: {BORDER};
                width: 5px;
            }}
            QSplitter::handle:horizontal:hover {{
                background: #0a84ff;
            }}
            QAbstractScrollArea::corner {{ background:{PANEL_BG}; border:none; }}
            QScrollBar:vertical {{
                background:{PANEL_BG}; width:6px; border-radius:3px;
            }}
            QScrollBar::handle:vertical {{
                background:{SCROLLBAR_HANDLE}; border-radius:3px; min-height:30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
            QScrollBar:horizontal {{
                background:{PANEL_BG}; height:6px; border-radius:3px;
            }}
            QScrollBar::handle:horizontal {{
                background:{SCROLLBAR_HANDLE}; border-radius:3px; min-width:30px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
            QProgressBar {{
                background:{INPUT_BG}; border:none; border-radius:3px; height:6px;
            }}
            QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #002b80, stop:1 #0055ff); border-radius:3px; }}
            QToolTip {{
                background-color: {"#2c2c2e" if CURRENT_THEME_MODE == "dark" else "#ffffff"};
                color: {"#ffffff" if CURRENT_THEME_MODE == "dark" else "#111827"};
                border: 1px solid {"#444446" if CURRENT_THEME_MODE == "dark" else "#cbd5e1"};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QMessageBox, QInputDialog {{
                background-color: {"#1e1e1e" if CURRENT_THEME_MODE == "dark" else "#ffffff"};
                color: {"#ffffff" if CURRENT_THEME_MODE == "dark" else "#000000"};
            }}
            QMessageBox QLabel, QInputDialog QLabel {{
                color: {"#ffffff" if CURRENT_THEME_MODE == "dark" else "#000000"};
                font-weight: 600;
                font-size: 13px;
            }}
            QInputDialog QLineEdit {{
                background-color: {INPUT_BG};
                color: {TEXT};
                border: 1.5px solid #0a84ff;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
            }}
        """)

    def _create_funny_pixel_robot_icon(self):
        """Draws a sharp, retro 8-bit style pixelated funny robot icon."""
        size = 28
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        scale = size / 16.0
        
        def fill_rect(x, y, w, h, color):
            painter.fillRect(QRect(int(x * scale), int(y * scale), int(w * scale), int(h * scale)), QColor(color))

        # Antenna
        fill_rect(7, 0, 2, 2, "#00e5ff") # Glowing cyan tip
        fill_rect(7, 2, 2, 2, "#78909c") # Metal stem
        
        # Head box
        fill_rect(3, 4, 10, 10, "#263238") # Dark head outline
        fill_rect(4, 5, 8, 8, "#455a64")   # Metallic face plate
        fill_rect(1, 7, 2, 3, "#ff9f0a")   # Left ear bolt
        fill_rect(13, 7, 2, 3, "#ff9f0a")  # Right ear bolt
        
        # Funny eyes visor
        fill_rect(4, 6, 8, 3, "#000000")   # Visor background
        fill_rect(5, 7, 2, 2, "#ffffff")   # Left eye white
        fill_rect(6, 7, 1, 1, "#00e5ff")   # Left pupil
        fill_rect(9, 7, 2, 2, "#ffffff")   # Right eye white
        fill_rect(9, 8, 1, 1, "#00e5ff")   # Right pupil (funny derpy eye!)
        
        # Pixelated funny mouth grin
        fill_rect(5, 10, 6, 2, "#102027")  # Mouth cavity
        fill_rect(6, 10, 1, 1, "#30d158")  # Teeth 1
        fill_rect(8, 10, 1, 1, "#30d158")  # Teeth 2
        fill_rect(10, 10, 1, 1, "#30d158") # Teeth 3

        painter.end()
        return pix

    def _build_ui(self):
        # Upper Window Toolbar
        self.tb = self.addToolBar("Main")
        self.tb.setMovable(False)
        self.tb.setFixedHeight(46)
        self.tb.setStyleSheet(f"QToolBar {{ background:{HEADER}; border-bottom:1px solid {BORDER}; spacing:6px; padding:4px 8px; }}")


        # 1. Left Side: Marko Polo Animated Assistant & Speech Bubble Cloud
        self.robot_widget = RobotMovieLabel()
        self.robot_widget.setToolTip("🤠 Marko Polo Assistant - Speech typewriter activates talking mouth animation!")
        self.robot_action = self.tb.addWidget(self.robot_widget)

        self.speech_bubble = SpeechBubbleCloud("Active Panel: Source (iPhone)")
        self.speech_bubble_action = self.tb.addWidget(self.speech_bubble)
        self.status_msg = self.speech_bubble

        # Expanding Spacer to push View buttons to the center
        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.tb.addWidget(spacer_left)

        # 2. Middle / Center: View label & Top view buttons (view: [Source] [↻ Refresh] [Local])
        self.view_label = QLabel("view:")
        self.view_label.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; font-weight:bold; padding-left:4px; padding-right:2px;")
        self.tb.addWidget(self.view_label)

        panel_toggle_style = f"""
            QPushButton {{ background:{BTN_BG}; color:{TEXT}; border:1px solid {BORDER};
                          border-radius:7px; padding:5px 10px; font-size:11px; font-weight:600; }}
            QPushButton:hover {{ background:{BTN_HOVER}; }}
            QPushButton:checked {{ background:{ACCENT}; color:white; border-color:{ACCENT}; }}
        """

        self.toggle_left_btn = QPushButton("Source")
        self.toggle_left_btn.setCheckable(True)
        self.toggle_left_btn.setChecked(True)
        self.toggle_left_btn.setStyleSheet(panel_toggle_style)
        self.toggle_left_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_left_btn.setToolTip("Show/hide Source panel")
        self.toggle_left_btn.clicked.connect(self._toggle_left_panel)
        self.tb.addWidget(self.toggle_left_btn)

        self.refresh_btn = QPushButton("↻ Refresh")
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{ background:{BTN_BG}; color:{TEXT}; border:1px solid {BORDER};
                          border-radius:7px; padding:5px 24px; min-width:90px; font-size:11px; font-weight:600; }}
            QPushButton:hover {{ background:{BTN_HOVER}; }}
        """)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setToolTip("Refresh both panels")
        self.refresh_btn.clicked.connect(self._refresh_both)
        self.tb.addWidget(self.refresh_btn)

        self.toggle_right_btn = QPushButton("Local")
        self.toggle_right_btn.setCheckable(True)
        self.toggle_right_btn.setChecked(True)
        self.toggle_right_btn.setStyleSheet(panel_toggle_style)
        self.toggle_right_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_right_btn.setToolTip("Show/hide Local panel")
        self.toggle_right_btn.clicked.connect(self._toggle_right_panel)
        self.tb.addWidget(self.toggle_right_btn)

        # Zero offset spacer to keep Refresh button perfectly centered over middle panel
        shift_spacer = QWidget()
        shift_spacer.setFixedWidth(0)
        self.tb.addWidget(shift_spacer)

        # Expanding Spacer to push Icon Size slider & Theme toggle to the far right
        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.tb.addWidget(spacer_right)

        # Thumbnail Resizing Slider (right-aligned, next to theme button)
        self.slider_lbl = QLabel("Icon Size: ")
        self.slider_lbl.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; padding-left:4px;")
        self.tb.addWidget(self.slider_lbl)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(80, 240)
        self.slider.setValue(140)
        self.slider.setFixedWidth(110)
        self.slider.setCursor(Qt.SizeHorCursor)
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: 1px solid {BORDER};
                height: 4px;
                background: {INPUT_BG};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {ACCENT2};
            }}
        """)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.tb.addWidget(self.slider)

        self.tb.addSeparator()

        # Theme Toggle Button (emoji-only, right-aligned)
        theme_icon = "☀️" if CURRENT_THEME_MODE == "dark" else "🌙"
        self.theme_btn = QPushButton(theme_icon)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setToolTip("Switch between Dark and Light mode")
        self.theme_btn.setStyleSheet(f"""
            QPushButton {{ background:{BTN_BG}; color:{TEXT}; border:1px solid {BORDER};
                          border-radius:7px; padding:6px 10px; font-size:14px; font-weight:600; }}
            QPushButton:hover {{ background:{BTN_HOVER}; }}
        """)
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.tb.addWidget(self.theme_btn)

        # Settings Button
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setToolTip("Open Settings")
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{ background:{BTN_BG}; color:{TEXT}; border:1px solid {BORDER};
                          border-radius:7px; padding:6px 10px; font-size:14px; font-weight:600; }}
            QPushButton:hover {{ background:{BTN_HOVER}; }}
        """)
        self.settings_btn.clicked.connect(self._open_settings)
        self.tb.addWidget(self.settings_btn)

        self.tb.addSeparator()

        # App settings state
        self._app_settings = {
            "dark_mode": CURRENT_THEME_MODE == "dark",
            "show_special_commands": False,
            "gjuro_mode": False,
            "sound_effects": True,
            "robot_tips": True,
            "compact_mode": False,
            "auto_refresh": False,
        }
        self._gjuro_mode_enabled = False
        self._robot_tips_enabled = True
        self._auto_refresh_enabled = False

        # Quit Button (always prominent in top-right corner)
        self.quit_btn = QPushButton("✕ Quit")
        self.quit_btn.setCursor(Qt.PointingHandCursor)
        self.quit_btn.setToolTip("Quit Marko Polo Explorer")
        self.quit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 69, 58, 0.18);
                color: #ff453a;
                border: 1.5px solid #ff453a;
                border-radius: 7px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 800;
                min-width: 60px;
            }}
            QPushButton:hover {{
                background-color: #ff453a;
                color: #ffffff;
                border-color: #ff453a;
            }}
        """)
        self.quit_btn.clicked.connect(self.close)
        self.tb.addWidget(self.quit_btn)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.hide()

        # Middle vertical button panel
        self.middle_panel = QFrame()
        self.middle_panel.setMinimumWidth(130)
        self.middle_panel.setMaximumWidth(350)

        mid_lay = QVBoxLayout(self.middle_panel)
        mid_lay.setContentsMargins(8, 10, 8, 10)
        mid_lay.setSpacing(10)

        # Plain gray text label at bottom of middle panel to move panel left or right
        self.move_panel_sign = MovePanelSign()
        mid_lay.addWidget(self.move_panel_sign)
        mid_lay.addSpacing(4)

        # Navigation buttons layout in middle panel
        nav_lay = QHBoxLayout()
        nav_lay.setSpacing(6)

        self.mid_back = QPushButton("<")
        self.mid_back.setCursor(Qt.PointingHandCursor)
        self.mid_back.clicked.connect(self._go_back_active)
        self.mid_back.setEnabled(False)

        self.mid_fwd = QPushButton(">")
        self.mid_fwd.setCursor(Qt.PointingHandCursor)
        self.mid_fwd.clicked.connect(self._go_forward_active)
        self.mid_fwd.setEnabled(False)

        nav_lay.addWidget(self.mid_back)
        nav_lay.addWidget(self.mid_fwd)

        self.mid_sel_all = QPushButton("Select All")
        self.mid_sel_all.clicked.connect(self._select_all_active)

        self.mid_desel_all = QPushButton("Deselect All")
        self.mid_desel_all.clicked.connect(self._deselect_all_active)

        self.mid_new_folder = QPushButton("New Folder")
        self.mid_new_folder.clicked.connect(self._create_new_folder)

        # Commands Expandable Container (sub-buttons show under button when clicked!)
        self.iphone_cmd_btn = QPushButton("📱 Commands ▼")
        self.iphone_cmd_btn.setCursor(Qt.PointingHandCursor)
        self.iphone_cmd_btn.setToolTip("Click to show/hide action commands")
        self.iphone_cmd_btn.clicked.connect(self._toggle_iphone_commands)

        self.iphone_container = QFrame()
        self.iphone_container.hide() # Collapsed by default
        iphone_lay = QVBoxLayout(self.iphone_container)
        iphone_lay.setContentsMargins(0, 2, 0, 2)
        iphone_lay.setSpacing(4)

        self.btn_copy_loc = QPushButton("Copy to Location")
        self.btn_copy_loc.setCursor(Qt.PointingHandCursor)
        copy_loc_alt = "HOW TO USE: 1) Select files in the iPhone/Source panel (use drag selection or Ctrl+Click). 2) Make sure the Local panel is showing your desired destination folder. 3) Click 'Copy to Location' — selected files will be downloaded and copied to the local folder."
        self.btn_copy_loc.setToolTip(copy_loc_alt)
        self.btn_copy_loc.installEventFilter(self)
        self.btn_copy_loc.clicked.connect(self._handle_copy_to_location_action)

        self.btn_compare_copy = QPushButton("Compare & Copy")
        self.btn_compare_copy.setCursor(Qt.PointingHandCursor)
        compare_alt = "HOW TO USE: 1) Make sure both panels are visible — Source (iPhone) on left, Local folder on right. 2) Click 'Compare & Copy' — it compares files between both panels by name and only copies files that are missing from the destination, skipping duplicates."
        self.btn_compare_copy.setToolTip(compare_alt)
        self.btn_compare_copy.installEventFilter(self)
        self.btn_compare_copy.clicked.connect(self._handle_compare_copy_action)

        iphone_lay.addWidget(self.btn_copy_loc)
        iphone_lay.addWidget(self.btn_compare_copy)

        # Special Commands Expandable Container (sub-buttons show under button when clicked!)
        self.special_cmd_btn = QPushButton("✨ Special Commands ▼")
        self.special_cmd_btn.setCursor(Qt.PointingHandCursor)
        self.special_cmd_btn.setToolTip("Click to show/hide Special action buttons")
        self.special_cmd_btn.clicked.connect(self._toggle_special_commands)
        self.special_cmd_btn.hide()  # Hidden by default

        self.special_container = QFrame()
        self.special_container.hide()  # Collapsed by default on app launch
        special_lay = QVBoxLayout(self.special_container)
        special_lay.setContentsMargins(0, 2, 0, 2)
        special_lay.setSpacing(4)

        self.btn_del_dups = QPushButton("Del duplicates (_1)")
        self.btn_del_dups.setCursor(Qt.PointingHandCursor)
        del_dups_alt = "HOW TO USE: 1) Navigate to a folder in the Local panel that has duplicate files (files ending with _1 before the extension, e.g. photo_1.jpg). 2) Click 'Del duplicates (_1)' — all duplicate files with the (_1) suffix will be automatically found and deleted."
        self.btn_del_dups.setToolTip(del_dups_alt)
        self.btn_del_dups.installEventFilter(self)
        self.btn_del_dups.clicked.connect(self._delete_duplicates_local)

        self.btn_magic = QPushButton("Magic Folders")
        self.btn_magic.setCursor(Qt.PointingHandCursor)
        magic_alt = "HOW TO USE: 1) Navigate to a folder with files in the Local panel. 2) Select files you want organized (or Select All). 3) Click 'Magic Folders' — files will be sorted into monthly subfolders (e.g. 2025-01, 2025-02) by date. You can undo this anytime with 'Undo Magic Folder'."
        self.btn_magic.setToolTip(magic_alt)
        self.btn_magic.installEventFilter(self)
        self.btn_magic.clicked.connect(self._magic_time_management)

        self.btn_undo_magic = QPushButton("Undo Magic Folder")
        self.btn_undo_magic.setCursor(Qt.PointingHandCursor)
        undo_alt = "HOW TO USE: 1) Navigate to the parent folder where Magic Folders was used. 2) Click 'Undo Magic Folder' — all files inside the date subfolders will be moved back to the main folder, and empty subfolders will be deleted automatically."
        self.btn_undo_magic.setToolTip(undo_alt)
        self.btn_undo_magic.installEventFilter(self)
        self.btn_undo_magic.clicked.connect(self._reverse_time_management)

        self.btn_extract_png = QPushButton("extract .png")
        self.btn_extract_png.setCursor(Qt.PointingHandCursor)
        extract_png_alt = "HOW TO USE: 1) Navigate to a folder containing mixed files in the Local panel. 2) Click 'extract .png' — all PNG image files will be moved into a separate 'png' subfolder automatically."
        self.btn_extract_png.setToolTip(extract_png_alt)
        self.btn_extract_png.installEventFilter(self)
        self.btn_extract_png.clicked.connect(self._extract_png)

        self.btn_extract_videos = QPushButton("extract videos")
        self.btn_extract_videos.setCursor(Qt.PointingHandCursor)
        extract_vid_alt = "HOW TO USE: 1) Navigate to a folder containing mixed files in the Local panel. 2) Click 'extract videos' — all video files (.mp4, .mov, .m4v, .mkv) will be moved into a separate 'videos' subfolder automatically."
        self.btn_extract_videos.setToolTip(extract_vid_alt)
        self.btn_extract_videos.installEventFilter(self)
        self.btn_extract_videos.clicked.connect(self._extract_videos)

        special_lay.addWidget(self.btn_del_dups)
        special_lay.addWidget(self.btn_magic)
        special_lay.addWidget(self.btn_undo_magic)
        special_lay.addWidget(self.btn_extract_png)
        special_lay.addWidget(self.btn_extract_videos)

        mid_lay.addLayout(nav_lay)
        mid_lay.addSpacing(6)

        # ── Circular Transfer Progress Widget (Placed on Top Over Select All) ──
        self.circular_progress = CircularTransferProgress()
        self.circular_progress.set_theme_mode(CURRENT_THEME_MODE)
        circle_container = QHBoxLayout()
        circle_container.setContentsMargins(0, 0, 0, 0)
        circle_container.addStretch()
        circle_container.addWidget(self.circular_progress)
        circle_container.addStretch()
        mid_lay.addLayout(circle_container)

        # ── Time Remaining ETA Label ──
        self.eta_label = QLabel("")
        self.eta_label.setAlignment(Qt.AlignCenter)
        self.eta_label.setStyleSheet("font-size: 10px; font-weight: 700; color: #30c7ff; font-family: 'SF Mono', Consolas, monospace;")
        self.eta_label.hide()
        mid_lay.addWidget(self.eta_label)

        # ── Transfer Control Buttons (Pause / Continue / Stop) ──
        self.transfer_controls = TransferControlButtons()
        self.transfer_controls.set_theme_mode(CURRENT_THEME_MODE)
        self.transfer_controls.pause_clicked.connect(self._on_transfer_pause)
        self.transfer_controls.continue_clicked.connect(self._on_transfer_continue)
        self.transfer_controls.stop_clicked.connect(self._on_transfer_stop)
        mid_lay.addWidget(self.transfer_controls)

        mid_lay.addSpacing(8)
        mid_lay.addWidget(self.mid_sel_all)
        mid_lay.addWidget(self.mid_desel_all)
        mid_lay.addSpacing(8)
        mid_lay.addWidget(self.mid_new_folder)
        mid_lay.addSpacing(10)
        mid_lay.addWidget(self.iphone_cmd_btn)
        mid_lay.addWidget(self.iphone_container)
        mid_lay.addSpacing(6)
        mid_lay.addWidget(self.special_cmd_btn)
        mid_lay.addWidget(self.special_container)
        mid_lay.addSpacing(10)
        mid_lay.addStretch(1)

        # Register button alt text summaries for Robot Speech Bubble typewriter display
        # Each button shows step-by-step instructions in the robot's speech cloud on hover
        self.register_button_alt_text(self.toggle_left_btn, "📱 Source Panel: Click to show or hide the left Source panel (iPhone/Camera Roll). Use this to focus on just the Local panel when you don't need the phone view.")
        self.register_button_alt_text(self.refresh_btn, "🔄 Refresh: Click to rescan all connected USB devices and refresh file listings in both panels. Use after plugging in a new device or if files appear missing.")
        self.register_button_alt_text(self.toggle_right_btn, "📂 Local Panel: Click to show or hide the right Local destination folder panel. Use this to focus on just the Source panel.")
        self.register_button_alt_text(self.theme_btn, "🎨 Theme: Click to switch between Dark Mode and Light Mode. Your preference is saved automatically for next launch.")
        self.register_button_alt_text(self.settings_btn, "⚙️ Settings: Open the Settings window to configure Dark Mode, Special Commands visibility, Sound Effects, Robot Tips, and more. Your preferences are saved automatically.")
        self.register_button_alt_text(self.quit_btn, "🚪 Quit: Click to save your current session (panel positions, folder paths, selections) and exit Marko Polo Explorer. Everything is restored on next launch!")
        self.register_button_alt_text(self.iphone_cmd_btn, "📱 iPhone Commands: Click to expand/collapse iPhone action buttons (Copy to Location, Compare & Copy). Use these to transfer files from your phone.")
        self.register_button_alt_text(self.btn_copy_loc, "📥 Copy to Location: HOW TO USE: 1) Select files in the iPhone/Source panel. 2) Navigate to your desired destination in the Local panel. 3) Click 'Copy to Location' — selected files will be copied to the local folder.")
        self.register_button_alt_text(self.btn_compare_copy, "🔍 Compare & Copy: HOW TO USE: 1) Make sure both panels are visible and navigated to folders. 2) Click 'Compare & Copy' — it will scan both panels and only copy files that are missing from the destination, skipping duplicates.")
        self.register_button_alt_text(self.special_cmd_btn, "✨ Special Commands: Click to expand/collapse special action buttons (Magic Folders, extract .png, extract videos, etc). These are power tools for organizing your files!")
        self.register_button_alt_text(self.btn_del_dups, "🗑️ Delete Duplicates: HOW TO USE: 1) Navigate to a folder in the Local panel that has duplicate files with (_1) suffix. 2) Click 'Del duplicates (_1)' — all files ending with _1 before the extension will be found and deleted.")
        self.register_button_alt_text(self.btn_magic, "🪄 Magic Folders: HOW TO USE: 1) Navigate to a folder with files in the Local panel. 2) Select the files you want organized (or use Select All). 3) Click 'Magic Folders' — files are sorted into monthly subfolders (e.g. 2025-01, 2025-02) by their date. Undo anytime with 'Undo Magic Folder'!")
        self.register_button_alt_text(self.btn_undo_magic, "↩️ Undo Magic Folder: HOW TO USE: 1) Navigate to the parent folder where you previously used Magic Folders. 2) Click 'Undo Magic Folder' — all files inside the date subfolders are moved back to the main folder, and empty subfolders are deleted automatically.")
        self.register_button_alt_text(self.btn_extract_png, "🖼️ Extract PNG: HOW TO USE: 1) Navigate to a folder containing mixed file types in the Local panel. 2) Click 'extract .png' — all PNG images will be moved into a new 'png' subfolder automatically.")
        self.register_button_alt_text(self.btn_extract_videos, "🎬 Extract Videos: HOW TO USE: 1) Navigate to a folder containing mixed file types in the Local panel. 2) Click 'extract videos' — all video files (.mp4, .mov, .m4v, .mkv) will be moved into a new 'videos' subfolder automatically.")
        self.register_button_alt_text(self.mid_back, "⬅️ Back: Click to go back to the previous folder in the active panel's navigation history. Keyboard shortcut: Backspace.")
        self.register_button_alt_text(self.mid_fwd, "➡️ Forward: Click to go forward in the active panel's navigation history after going back.")
        self.register_button_alt_text(self.mid_sel_all, "☑️ Select All: Click to select all files in the currently active panel. Useful before using Magic Folders, Copy, or other batch operations.")
        self.register_button_alt_text(self.mid_desel_all, "⬜ Deselect All: Click to clear all file selections in the currently active panel.")
        self.register_button_alt_text(self.mid_new_folder, "📁 New Folder: Click to create a new subfolder inside the current directory of the active Local panel. A dialog will ask you for the folder name.")
        self.register_button_alt_text(self.move_panel_sign, "↔️ Move Panel: Click and drag this sign left or right to resize the middle panel position between the two file panels.")

        if hasattr(self, "iphone_panel"):
            self.register_button_alt_text(self.iphone_panel.up_btn, "⬆️ Up: Click to navigate up to the parent directory in the Source panel.")
            self.register_button_alt_text(self.iphone_panel.back_btn, "⬅️ Back: Go back to the previous folder you were viewing in the Source panel.")
            self.register_button_alt_text(self.iphone_panel.fwd_btn, "➡️ Forward: Go forward in Source panel folder history after going back.")
            self.register_button_alt_text(self.iphone_panel.grid_btn, "🔲 Grid View: Switch the Source panel to thumbnail grid view for visual browsing of photos and videos.")
            self.register_button_alt_text(self.iphone_panel.list_btn, "📋 List View: Switch the Source panel to detailed list view showing file names, sizes, and dates in columns.")
            self.register_button_alt_text(self.iphone_panel.preview_btn, "👁️ Preview: Toggle the preview sidebar in the Source panel. Select a file to see a large preview, EXIF data, and GPS location.")
            if hasattr(self.iphone_panel, "add_src_btn"):
                self.register_button_alt_text(self.iphone_panel.add_src_btn, "➕ Add Source: Click to add a local folder or connected device as an additional source in the Source panel.")

        if hasattr(self, "local_panel"):
            self.register_button_alt_text(self.local_panel.up_btn, "⬆️ Up: Click to navigate up to the parent directory in the Local panel.")
            self.register_button_alt_text(self.local_panel.back_btn, "⬅️ Back: Go back to the previous folder you were viewing in the Local panel.")
            self.register_button_alt_text(self.local_panel.fwd_btn, "➡️ Forward: Go forward in Local panel folder history after going back.")
            self.register_button_alt_text(self.local_panel.grid_btn, "🔲 Grid View: Switch the Local panel to thumbnail grid view for visual browsing.")
            self.register_button_alt_text(self.local_panel.list_btn, "📋 List View: Switch the Local panel to detailed list view showing file names, sizes, and dates.")
            self.register_button_alt_text(self.local_panel.preview_btn, "👁️ Preview: Toggle the preview sidebar in the Local panel. Select a file to see a large preview and details.")
            if hasattr(self.local_panel, "browse_btn"):
                self.register_button_alt_text(self.local_panel.browse_btn, "📂 Browse: Click to open a folder picker dialog and select a different local destination directory.")

        self._style_middle_panel()

    def _style_middle_panel(self):
        """Apply theme-aware styles to the middle button panel and all its buttons."""
        self.middle_panel.setStyleSheet(f"""
            QFrame {{
                background: {HEADER};
                border-left: 1px solid {BORDER};
                border-right: 1px solid {BORDER};
            }}
        """)
        if hasattr(self, "move_panel_sign"):
            self.move_panel_sign.set_theme_mode(CURRENT_THEME_MODE)

        def mid_btn_style(color):
            btn_bg = "rgba(0, 0, 0, 0.05)" if CURRENT_THEME_MODE == "light" else "rgba(255, 255, 255, 0.05)"
            hover_text = "black" if color in ["#30d158", "#ff9f0a", "#30c7ff"] or CURRENT_THEME_MODE == "light" else "white"
            return f"""
                QPushButton {{
                    background: {btn_bg};
                    color: {TEXT};
                    border: 1px solid {BORDER};
                    border-bottom: 3px solid {color};
                    border-radius: 5px;
                    padding: 8px 6px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {color};
                    color: {hover_text};
                    border-color: {color};
                }}
            """

        def nav_btn_style(color):
            btn_bg = "rgba(0, 0, 0, 0.05)" if CURRENT_THEME_MODE == "light" else "rgba(255, 255, 255, 0.05)"
            disabled_text = "rgba(0, 0, 0, 0.25)" if CURRENT_THEME_MODE == "light" else "rgba(255, 255, 255, 0.25)"
            disabled_bg = "rgba(0, 0, 0, 0.02)" if CURRENT_THEME_MODE == "light" else "rgba(255, 255, 255, 0.02)"
            disabled_border = "rgba(0, 0, 0, 0.08)" if CURRENT_THEME_MODE == "light" else "rgba(255, 255, 255, 0.08)"
            hover_text = "white" if CURRENT_THEME_MODE == "dark" else "black"
            return f"""
                QPushButton {{
                    background: {btn_bg};
                    color: {TEXT};
                    border: 1px solid {BORDER};
                    border-bottom: 3px solid {color};
                    border-radius: 5px;
                    padding: 8px 6px;
                    font-size: 11px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {color};
                    color: {hover_text};
                    border-color: {color};
                }}
                QPushButton:disabled {{
                    color: {disabled_text};
                    background: {disabled_bg};
                    border-color: {disabled_border};
                    border-bottom: 3px solid {disabled_border};
                }}
            """

        self.mid_back.setStyleSheet(nav_btn_style(ACCENT))
        self.mid_fwd.setStyleSheet(nav_btn_style(ACCENT))

        self.mid_sel_all.setStyleSheet(mid_btn_style(ACCENT))
        self.mid_desel_all.setStyleSheet(mid_btn_style(SUBTEXT))
        self.mid_new_folder.setStyleSheet(mid_btn_style("#30d158"))

        self.iphone_cmd_btn.setStyleSheet(mid_btn_style(ACCENT))
        self.btn_copy_loc.setStyleSheet(mid_btn_style(ACCENT))
        self.btn_compare_copy.setStyleSheet(mid_btn_style(ACCENT))

        self.special_cmd_btn.setStyleSheet(mid_btn_style("#af52de"))
        self.btn_del_dups.setStyleSheet(mid_btn_style("#ff9f0a"))
        self.btn_magic.setStyleSheet(mid_btn_style("#af52de"))
        self.btn_undo_magic.setStyleSheet(mid_btn_style("#af52de"))
        self.btn_extract_png.setStyleSheet(mid_btn_style("#af52de"))
        self.btn_extract_videos.setStyleSheet(mid_btn_style("#af52de"))

        # Splitter panels
        self.iphone_panel = FilePanel(is_left=True)
        self.iphone_panel.device_changed.connect(self._on_device_selected)
        self.iphone_panel.focused.connect(lambda: self._set_active_panel("left"))
        
        self.local_panel = FilePanel(is_left=False)
        self.local_panel.focused.connect(lambda: self._set_active_panel("right"))

        self.iphone_panel.set_focused(True)
        self.local_panel.set_focused(False)

        # Event filters for table keypresses
        self.iphone_panel.table.installEventFilter(self)
        self.local_panel.table.installEventFilter(self)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.iphone_panel)
        self.splitter.addWidget(self.middle_panel)
        self.splitter.addWidget(self.local_panel)
        self.splitter.setCollapsible(0, True)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, True)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes([550, 150, 550])
        self.splitter.splitterMoved.connect(self._on_main_splitter_moved)

        # Store default splitter sizes for restoring
        self._default_splitter_sizes = [550, 150, 550]
        # Track user's manually set splitter sizes (None = use default centering)
        self._user_splitter_sizes = None
        self._left_visible = True
        self._right_visible = True

        central = QWidget()
        vl = QVBoxLayout(central)
        vl.setContentsMargins(0,0,0,0)
        vl.setSpacing(0)
        vl.addWidget(self.progress)
        vl.addWidget(self.splitter, 1)
        self.setCentralWidget(central)
        self._update_middle_nav_buttons()

    # ── Auto-Update System ────────────────────────────────────────────────────
    def _check_for_updates(self, silent=True):
        self.check_thread = CheckUpdateThread(current_version=__version__)
        if not silent:
            if hasattr(self, "speech_bubble"):
                self.speech_bubble.set_speech_text("🔍 Checking server for updates...")
        self.check_thread.update_found.connect(lambda data: self._on_update_found_silent(data) if silent else self._on_update_found(data))
        self.check_thread.no_update.connect(lambda: None if silent else self._on_no_update())
        self.check_thread.start()

    def _on_update_found(self, data):
        self.update_info = data
        remote_ver = data.get("version", "new")
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.set_speech_text(f"🚀 Update v{remote_ver} available!")
        self._open_update_popup_dialog()

    def _on_update_found_silent(self, data):
        self.update_info = data
        remote_ver = data.get("version", "new")
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.set_speech_text(f"🚀 Update v{remote_ver} available! Click Update button!")

    def _on_no_update(self):
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.set_speech_text("✅ You are using the latest version!")
        QMessageBox.information(self, "Update Check", f"You have the latest version (v{__version__}).")

    def _open_update_popup_dialog(self):
        dlg = UpdateCheckDialog(current_version=__version__, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.update_info:
            self.update_info = dlg.update_info
            self._start_update_download()

    def _start_update_download(self):
        if not hasattr(self, "update_info") or not self.update_info:
            return
        os_key = "mac" if sys.platform == "darwin" else "windows"
        os_data = self.update_info.get(os_key, {})
        download_url = os_data.get("url")
        if not download_url:
            QMessageBox.warning(self, "Update Error", f"No update download URL found for {os_key.upper()}.")
            return

        if hasattr(self, "speech_bubble"):
            self.speech_bubble.set_speech_text("⬇️ Downloading update... Please wait...")

        self.dl_thread = DownloadUpdateThread(download_url)
        self.dl_thread.progress_signal.connect(self._on_download_progress)
        self.dl_thread.download_finished.connect(self._on_download_finished)
        self.dl_thread.download_failed.connect(self._on_download_failed)
        self.dl_thread.start()

    def _on_download_progress(self, downloaded, total):
        if total > 0:
            pct = int((downloaded / total) * 100)
            if hasattr(self, "speech_bubble"):
                self.speech_bubble.set_speech_text(f"⬇️ Downloading update... {pct}% ({downloaded // 1024} KB / {total // 1024} KB)")

    def _on_download_failed(self, err):
        QMessageBox.critical(self, "Download Failed", f"Failed to download update package:\n{err}")
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.set_speech_text("❌ Update download failed.")

    def _on_download_finished(self, zip_path):
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.set_speech_text("⚡ Update downloaded! Restarting application...")

        # Detect if running as Nuitka standalone (frozen) build
        is_nuitka = getattr(sys, "frozen", False) or "__compiled__" in dir()

        if is_nuitka and sys.platform == "win32":
            # Nuitka standalone Windows: use batch script to replace the .exe and relaunch
            self._apply_nuitka_update(zip_path)
        else:
            # Regular Python environment: use updater.py
            updater_py = os.path.join(script_dir, "updater.py")

            # Determine restart launch command
            if sys.platform == "darwin":
                app_bundle = os.path.join(script_dir, "Marko Polo Explorer v1.0.app")
                if os.path.exists(app_bundle):
                    launch_cmd = f'open -n "{app_bundle}"'
                else:
                    launch_cmd = f'"{sys.executable}" "{os.path.join(script_dir, "image_capture_app.py")}"'
            else:
                bat_file = os.path.join(script_dir, "run_app.bat")
                if os.path.exists(bat_file):
                    launch_cmd = f'"{bat_file}"'
                else:
                    launch_cmd = f'"{sys.executable}" "{os.path.join(script_dir, "image_capture_app.py")}"'

            cmd = [sys.executable, updater_py, "--zip", zip_path, "--target", script_dir, "--pid", str(os.getpid()), "--launch", launch_cmd]
            try:
                subprocess.Popen(cmd, cwd=script_dir)
            except Exception as e:
                QMessageBox.critical(self, "Update Error", f"Failed to launch updater: {e}")
                return

            QApplication.quit()

    def _apply_nuitka_update(self, zip_path):
        """Apply update for Nuitka standalone Windows build.
        
        Downloads are ZIP files containing a program/ subfolder.
        Extracts updated files (image assets, version.json, etc.) and if a new
        MarkoPoloExplorer.exe is included, replaces the running executable via a
        temporary batch script (since a running .exe can't overwrite itself).
        """
        import zipfile as zf

        current_exe = os.path.abspath(sys.executable)
        app_dir = os.path.dirname(current_exe)
        tmp_dir = tempfile.mkdtemp(prefix="markopolo_update_")

        try:
            with zf.ZipFile(zip_path, 'r') as z:
                all_names = z.namelist()
                has_program = any(n.startswith("program/") for n in all_names)

                for member in z.infolist():
                    if member.is_dir():
                        continue

                    # Determine actual relative path
                    if has_program:
                        if not member.filename.startswith("program/"):
                            continue
                        rel = member.filename[len("program/"):]
                    else:
                        rel = member.filename

                    if not rel:
                        continue

                    out = os.path.join(tmp_dir, rel)
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    with z.open(member) as src, open(out, 'wb') as dst:
                        dst.write(src.read())

            # Build batch script that waits for this process to exit, then copies files and relaunches
            bat_path = os.path.join(tmp_dir, "_update.bat")
            exe_name = os.path.basename(current_exe)

            bat_lines = [
                "@echo off",
                "echo Applying Marko Polo Explorer update...",
                f'ping 127.0.0.1 -n 3 > nul',  # wait ~2 seconds for app to close
                "",
                "rem Copy all extracted files to app directory",
            ]

            # Copy all extracted files
            for root, dirs, files in os.walk(tmp_dir):
                for fn in files:
                    if fn == "_update.bat":
                        continue
                    src = os.path.join(root, fn)
                    rel = os.path.relpath(src, tmp_dir)
                    dst = os.path.join(app_dir, rel)
                    bat_lines.append(f'mkdir "{os.path.dirname(dst)}" 2>nul')
                    bat_lines.append(f'copy /y "{src}" "{dst}"')

            # Relaunch the app
            bat_lines.append("")
            bat_lines.append(f'start "" "{current_exe}"')
            bat_lines.append("")
            bat_lines.append("rem Clean up temp files")
            bat_lines.append(f'rmdir /s /q "{tmp_dir}"')
            bat_lines.append(f'del "%~f0"')

            with open(bat_path, 'w') as f:
                f.write('\n'.join(bat_lines))

            # Remove downloaded zip
            try:
                os.remove(zip_path)
            except Exception:
                pass

            # Launch the updater batch and quit
            subprocess.Popen(
                ['cmd', '/c', bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000,
                cwd=tmp_dir
            )
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Failed to apply standalone update:\n{e}")
            return

        QApplication.quit()

    def _on_slider_changed(self, val):
        if hasattr(self, "iphone_panel") and self.iphone_panel.view_mode != "grid":
            self.iphone_panel.set_view_mode("grid")
        if hasattr(self, "local_panel") and self.local_panel.view_mode != "grid":
            self.local_panel.set_view_mode("grid")
        self.resize_timer.start()

    def _switch_active_to_list_mode(self):
        if hasattr(self, "iphone_panel") and self.iphone_panel.view_mode != "details":
            self.iphone_panel.set_view_mode("details")
        if hasattr(self, "local_panel") and self.local_panel.view_mode != "details":
            self.local_panel.set_view_mode("details")

    def _apply_thumb_resize(self):
        global THUMB_SIZE
        THUMB_SIZE = self.slider.value()
        # Refresh both lists/grids
        self.iphone_panel._rebuild()
        self.local_panel._rebuild()

    def _update_active_status_text(self):
        """Updates speech bubble cloud text with typewriter effect and triggers robot blink GIF."""
        if not hasattr(self, "speech_bubble"):
            return
        if self.active_panel == "left":
            if getattr(self.iphone_panel, "mode", "local") == "local":
                loc_path = self.iphone_panel.current_path if hasattr(self, "iphone_panel") else "Source"
                folder_name = os.path.basename(loc_path) or loc_path
                sz_info = self.iphone_panel.count_lbl.text() if hasattr(self, "iphone_panel") else ""
                if "(" in sz_info and ")" in sz_info:
                    sz_part = sz_info[sz_info.find("(")+1:sz_info.find(")")]
                    self.speech_bubble.setText(f"Active Panel: Source ({folder_name} • {sz_part})")
                else:
                    self.speech_bubble.setText(f"Active Panel: Source ({folder_name})")
            else:
                dev_name = self.current_camera.name() if (hasattr(self, "current_camera") and self.current_camera) else "iPhone / Camera Roll"
                sz_info = self.iphone_panel.count_lbl.text() if hasattr(self, "iphone_panel") else ""
                if "(" in sz_info and ")" in sz_info:
                    sz_part = sz_info[sz_info.find("(")+1:sz_info.find(")")]
                    self.speech_bubble.setText(f"Active Panel: Source ({dev_name} • {sz_part})")
                else:
                    self.speech_bubble.setText(f"Active Panel: Source ({dev_name})")
        else:
            loc_path = self.local_panel.current_path if hasattr(self, "local_panel") else "Local Destination"
            folder_name = os.path.basename(loc_path) or loc_path
            sz_info = self.local_panel.count_lbl.text() if hasattr(self, "local_panel") else ""
            if "(" in sz_info and ")" in sz_info:
                sz_part = sz_info[sz_info.find("(")+1:sz_info.find(")")]
                self.speech_bubble.setText(f"Active Panel: Local ({folder_name} • {sz_part})")
            else:
                self.speech_bubble.setText(f"Active Panel: Local ({folder_name})")
        
        if hasattr(self, "robot_widget"):
            self.robot_widget.trigger_blink()

    def _update_slider_visibility(self):
        """Show Icon Size slider ONLY when the active panel is in Grid mode."""
        if not hasattr(self, "slider") or not hasattr(self, "slider_lbl"):
            return
        active_p = self.iphone_panel if self.active_panel == "left" else self.local_panel
        is_grid = getattr(active_p, "view_mode", "grid") == "grid"
        self.slider_lbl.setVisible(is_grid)
        self.slider.setVisible(is_grid)

    def _set_active_panel(self, panel_name):
        if self.active_panel != panel_name:
            self.active_panel = panel_name
            if panel_name == "left":
                self.iphone_panel.set_focused(True)
                self.local_panel.set_focused(False)
            else:
                self.iphone_panel.set_focused(False)
                self.local_panel.set_focused(True)
            self._update_active_status_text()
            self._update_slider_visibility()
            self._update_middle_nav_buttons()

    def _go_back_active(self):
        active_panel = self.iphone_panel if self.active_panel == "left" else self.local_panel
        if hasattr(active_panel, "history_index") and active_panel.history_index > 0:
            active_panel._go_back()
        elif hasattr(active_panel, "_go_up"):
            active_panel._go_up()

    def _go_forward_active(self):
        active_panel = self.iphone_panel if self.active_panel == "left" else self.local_panel
        if hasattr(active_panel, "open_highlighted_item_or_go_forward"):
            active_panel.open_highlighted_item_or_go_forward()
        elif hasattr(active_panel, "open_selected_folder_or_go_forward"):
            active_panel.open_selected_folder_or_go_forward()
        elif hasattr(active_panel, "history_index") and hasattr(active_panel, "history") and active_panel.history_index < len(active_panel.history) - 1:
            active_panel._go_forward()
        self._update_middle_nav_buttons()

    def _update_middle_nav_buttons(self):
        if self.active_panel == "left":
            active_panel = self.iphone_panel
        else:
            active_panel = self.local_panel
            
        if hasattr(self, "mid_back") and hasattr(self, "mid_fwd"):
            self.mid_back.setEnabled(active_panel.history_index > 0)
            self.mid_fwd.setEnabled(active_panel.history_index < len(active_panel.history) - 1)

    def _toggle_active_panel(self):
        if self.active_panel == "left":
            self._set_active_panel("right")
        else:
            self._set_active_panel("left")

    def _toggle_left_panel(self):
        """Toggle the left (Source) panel visibility."""
        show = self.toggle_left_btn.isChecked()
        self._left_visible = show
        if show:
            self.iphone_panel.show()
        else:
            self.iphone_panel.hide()
            # If hiding the active panel, switch to the other one
            if self.active_panel == "left" and self._right_visible:
                self._set_active_panel("right")
        self._update_splitter_sizes(force_reset=True)

    def _toggle_right_panel(self):
        """Toggle the right (Local) panel visibility."""
        show = self.toggle_right_btn.isChecked()
        self._right_visible = show
        if show:
            self.local_panel.show()
        else:
            self.local_panel.hide()
            # If hiding the active panel, switch to the other one
            if self.active_panel == "right" and self._left_visible:
                self._set_active_panel("left")
        self._update_splitter_sizes(force_reset=True)

    def _on_main_splitter_moved(self, pos, index):
        """Store user's manual splitter position so resizes preserve it."""
        try:
            if hasattr(self, "splitter") and self.splitter is not None:
                self._user_splitter_sizes = self.splitter.sizes()
        except Exception:
            pass

    def _update_splitter_sizes(self, force_reset=False):
        """Redistribute splitter space based on which panels are visible.
        
        If the user has manually positioned the splitter (via drag or session restore),
        preserve their proportions on window resize. Only do a full equal-split reset
        when force_reset=True (panel toggle) or when no user position exists.
        """
        try:
            if not hasattr(self, "splitter") or self.splitter is None:
                return
            total = self.splitter.width()
            if total <= 0:
                return

            left_v = getattr(self, "_left_visible", True)
            right_v = getattr(self, "_right_visible", True)
            user_sizes = getattr(self, "_user_splitter_sizes", None)

            # If user has set a position and we're not forcing a reset, preserve proportions
            if user_sizes and not force_reset and left_v and right_v:
                old_total = sum(user_sizes)
                if old_total > 0:
                    ratio_left = user_sizes[0] / old_total
                    ratio_mid = user_sizes[1] / old_total
                    ratio_right = user_sizes[2] / old_total
                    new_left = max(50, int(total * ratio_left))
                    new_mid = max(130, int(total * ratio_mid))
                    new_right = max(50, total - new_left - new_mid)
                    self.splitter.setSizes([new_left, new_mid, new_right])
                    return

            mid_w = 150
            if left_v and right_v:
                panel_w = max(50, (total - mid_w) // 2)
                self.splitter.setSizes([panel_w, mid_w, panel_w])
            elif left_v and not right_v:
                self.splitter.setSizes([max(0, total - mid_w), mid_w, 0])
            elif not left_v and right_v:
                self.splitter.setSizes([0, mid_w, max(0, total - mid_w)])
            else:
                self.splitter.setSizes([0, mid_w, 0])

            # After a forced reset, clear user sizes so the new layout becomes the baseline
            if force_reset:
                self._user_splitter_sizes = None
        except Exception as e:
            print(f"Error in _update_splitter_sizes: {e}")

    def _toggle_theme(self):
        """Switch between dark and light themes."""
        new_mode = "light" if CURRENT_THEME_MODE == "dark" else "dark"
        set_theme(new_mode)
        # Update button emoji (no text label)
        self.theme_btn.setText("☀️" if new_mode == "dark" else "🌙")
        # Sync settings state
        if hasattr(self, '_app_settings'):
            self._app_settings['dark_mode'] = (new_mode == "dark")
        self._restyle_all()

    def _open_settings(self):
        """Open the Settings dialog."""
        # Sync current state into settings dict
        self._app_settings['dark_mode'] = (CURRENT_THEME_MODE == "dark")
        self._app_settings['show_special_commands'] = self.special_cmd_btn.isVisible()
        self._app_settings['gjuro_mode'] = getattr(self, '_gjuro_mode_enabled', False)
        self._app_settings['robot_tips'] = getattr(self, '_robot_tips_enabled', True)
        self._app_settings['auto_refresh'] = getattr(self, '_auto_refresh_enabled', False)

        dlg = SettingsDialog(parent=self, settings=dict(self._app_settings))
        dlg.theme_changed.connect(self._on_settings_theme_changed)
        dlg.special_commands_changed.connect(self._on_settings_special_commands)
        dlg.gjuro_mode_changed.connect(self._on_settings_gjuro_mode)
        dlg.sound_effects_changed.connect(self._on_settings_sound_effects)
        dlg.robot_tips_changed.connect(self._on_settings_robot_tips)
        dlg.compact_mode_changed.connect(self._on_settings_compact_mode)
        dlg.auto_refresh_changed.connect(self._on_settings_auto_refresh)
        dlg.exec()
        # Update settings from dialog
        self._app_settings.update(dlg.get_settings())

    def _on_settings_theme_changed(self, mode):
        """Handle theme change from Settings dialog."""
        if mode != CURRENT_THEME_MODE:
            set_theme(mode)
            self.theme_btn.setText("☀️" if mode == "dark" else "🌙")
            self._app_settings['dark_mode'] = (mode == "dark")
            self._restyle_all()

    def _on_settings_special_commands(self, visible):
        """Show or hide Special Commands button based on settings toggle."""
        self._app_settings['show_special_commands'] = visible
        if visible:
            self.special_cmd_btn.show()
        else:
            self.special_cmd_btn.hide()
            self.special_container.hide()
            self.special_cmd_btn.setText("✨ Special Commands ▼")

    def _on_settings_gjuro_mode(self, enabled):
        """Toggle Gjuro Mode (WASD keyboard navigation)."""
        self._app_settings['gjuro_mode'] = enabled
        self._gjuro_mode_enabled = enabled

    def _on_settings_sound_effects(self, enabled):
        """Toggle sound effects."""
        self._app_settings['sound_effects'] = enabled

    def _on_settings_robot_tips(self, enabled):
        """Toggle robot assistant and speech bubble visibility in the toolbar."""
        self._app_settings['robot_tips'] = enabled
        self._robot_tips_enabled = enabled
        if hasattr(self, "robot_action") and self.robot_action:
            self.robot_action.setVisible(enabled)
        if hasattr(self, "speech_bubble_action") and self.speech_bubble_action:
            self.speech_bubble_action.setVisible(enabled)
        if hasattr(self, "robot_widget") and self.robot_widget:
            self.robot_widget.setVisible(enabled)
            if not enabled:
                self.robot_widget.stop_animation()
        if hasattr(self, "speech_bubble") and self.speech_bubble:
            self.speech_bubble.setVisible(enabled)
            if not enabled:
                self.speech_bubble.type_timer.stop()

    def _on_settings_compact_mode(self, enabled):
        """Toggle compact mode (reduced padding/spacing)."""
        self._app_settings['compact_mode'] = enabled
        # Future: Adjust padding throughout the UI

    def _on_settings_auto_refresh(self, enabled):
        """Toggle auto-refresh of file panels."""
        self._app_settings['auto_refresh'] = enabled
        self._auto_refresh_enabled = enabled

    def _restyle_all(self):
        """Re-apply all styles throughout the app after a theme change."""
        # Main window base styles
        self._setup_style()

        # Toolbar
        self.tb.setStyleSheet(f"""
            QToolBar {{ background:{HEADER}; border-bottom:1px solid {BORDER}; spacing:6px; padding:4px 8px; }}
            QToolBar::separator {{ background:{BORDER}; width:1px; margin:4px 2px; }}
        """)

        # Toolbar buttons
        self.theme_btn.setStyleSheet(f"""
            QPushButton {{ background:{BTN_BG}; color:{TEXT}; border:1px solid {BORDER};
                          border-radius:7px; padding:6px 10px; font-size:14px; font-weight:600; }}
            QPushButton:hover {{ background:{BTN_HOVER}; }}
        """)
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{ background:{BTN_BG}; color:{TEXT}; border:1px solid {BORDER};
                          border-radius:7px; padding:6px 10px; font-size:14px; font-weight:600; }}
            QPushButton:hover {{ background:{BTN_HOVER}; }}
        """)
        self.quit_btn.setStyleSheet(f"""
            QPushButton {{ background:{BTN_BG}; color:#ff453a; border:1px solid #ff453a;
                          border-radius:7px; padding:6px 14px; font-size:11px; font-weight:700; }}
            QPushButton:hover {{ background:#ff453a; color:white; border-color:#ff453a; }}
        """)

        self.slider_lbl.setStyleSheet(f"color:{TEXT}; font-size:11px; font-weight:600; padding-left:4px;")
        self.slider.setStyleSheet(f"""
            QSlider {{ background: transparent; }}
            QSlider::groove:horizontal {{
                border: 1px solid {BORDER};
                height: 4px;
                background: {INPUT_BG};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {ACCENT2};
            }}
        """)

        if hasattr(self, "speech_bubble"):
            self.speech_bubble.set_theme_mode(CURRENT_THEME_MODE)

        # Circular progress and transfer control theme
        if hasattr(self, "circular_progress"):
            self.circular_progress.set_theme_mode(CURRENT_THEME_MODE)
        if hasattr(self, "transfer_controls"):
            self.transfer_controls.set_theme_mode(CURRENT_THEME_MODE)

        # Middle panel
        self._style_middle_panel()

        # File panels
        self.iphone_panel._restyle()
        self.local_panel._restyle()

        # Re-set focus highlight
        if self.active_panel == "left":
            self.iphone_panel.set_focused(True)
            self.local_panel.set_focused(False)
        else:
            self.iphone_panel.set_focused(False)
            self.local_panel.set_focused(True)

    def _save_session(self):
        """Save current workspace setup, session variables, and settings toggles to JSON file."""
        try:
            session_file = os.path.join(script_dir, "marko_polo_session.json")

            # Ensure latest settings state is fully synced before saving
            if not hasattr(self, '_app_settings'):
                self._app_settings = {}
            self._app_settings['dark_mode'] = (CURRENT_THEME_MODE == "dark")
            self._app_settings['show_special_commands'] = bool(getattr(self.special_cmd_btn, "isVisible", lambda: False)())
            self._app_settings['gjuro_mode'] = bool(getattr(self, '_gjuro_mode_enabled', False))
            self._app_settings['sound_effects'] = bool(self._app_settings.get('sound_effects', True))
            self._app_settings['robot_tips'] = bool(getattr(self, '_robot_tips_enabled', True))
            self._app_settings['compact_mode'] = bool(self._app_settings.get('compact_mode', False))
            self._app_settings['auto_refresh'] = bool(getattr(self, '_auto_refresh_enabled', False))

            data = {
                "theme": CURRENT_THEME_MODE,
                "left_path": self.iphone_panel.current_path if getattr(self.iphone_panel, "mode", "local") == "local" else "",
                "right_path": self.local_panel.current_path,
                "active_panel": self.active_panel,
                "left_view_mode": self.iphone_panel.view_mode,
                "right_view_mode": self.local_panel.view_mode,
                "left_preview": self.iphone_panel.preview_btn.isChecked(),
                "right_preview": self.local_panel.preview_btn.isChecked(),
                "left_visible": self._left_visible,
                "right_visible": self._right_visible,
                "icon_size": self.slider.value(),
                "splitter_sizes": self.splitter.sizes(),
                "geometry": [self.x(), self.y(), self.width(), self.height()],
                "app_settings": dict(self._app_settings)
            }
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving session: {e}")

    def _restore_session(self):
        """Restore workspace setup and session variables from JSON file if available."""
        session_file = os.path.join(script_dir, "marko_polo_session.json")
        if not os.path.exists(session_file):
            return
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 1. Theme
            theme = data.get("theme", "light")
            if theme != CURRENT_THEME_MODE:
                set_theme(theme)
                self.theme_btn.setText("☀️" if theme == "dark" else "🌙")
                self._restyle_all()

            # 1b. App settings
            saved_settings = data.get("app_settings", {})
            if saved_settings and hasattr(self, '_app_settings'):
                self._app_settings.update(saved_settings)
                # Sync dark mode flag with actual theme
                self._app_settings['dark_mode'] = (CURRENT_THEME_MODE == "dark")
                # Apply special commands visibility (default OFF)
                if not self._app_settings.get('show_special_commands', False):
                    self.special_cmd_btn.hide()
                    self.special_container.hide()
                else:
                    self.special_cmd_btn.show()
                # Apply Gjuro mode setting
                self._gjuro_mode_enabled = self._app_settings.get('gjuro_mode', False)
                # Apply robot tips setting & update widget visibility
                self._robot_tips_enabled = self._app_settings.get('robot_tips', True)
                if hasattr(self, "robot_action") and self.robot_action:
                    self.robot_action.setVisible(self._robot_tips_enabled)
                if hasattr(self, "speech_bubble_action") and self.speech_bubble_action:
                    self.speech_bubble_action.setVisible(self._robot_tips_enabled)
                if hasattr(self, "robot_widget") and self.robot_widget:
                    self.robot_widget.setVisible(self._robot_tips_enabled)
                    if not self._robot_tips_enabled:
                        self.robot_widget.stop_animation()
                if hasattr(self, "speech_bubble") and self.speech_bubble:
                    self.speech_bubble.setVisible(self._robot_tips_enabled)
                    if not self._robot_tips_enabled:
                        self.speech_bubble.type_timer.stop()
                # Apply auto-refresh setting
                self._auto_refresh_enabled = self._app_settings.get('auto_refresh', False)

            # 2. Icon size slider
            icon_size = data.get("icon_size")
            if icon_size and isinstance(icon_size, int):
                self.slider.setValue(icon_size)

            # 3. Paths
            left_path = data.get("left_path")
            if left_path and os.path.exists(left_path) and os.path.isdir(left_path):
                self.iphone_panel.load_path(left_path)

            right_path = data.get("right_path")
            if right_path and os.path.exists(right_path) and os.path.isdir(right_path):
                self.local_panel.load_path(right_path)

            # 4. View modes
            left_vm = data.get("left_view_mode")
            if left_vm in ("grid", "details") and self.iphone_panel.view_mode != left_vm:
                self.iphone_panel._toggle_view_mode()

            right_vm = data.get("right_view_mode")
            if right_vm in ("grid", "details") and self.local_panel.view_mode != right_vm:
                self.local_panel._toggle_view_mode()

            self._update_slider_visibility()

            # 5. Previews
            if data.get("left_preview"):
                self.iphone_panel.preview_btn.setChecked(True)
                self.iphone_panel._toggle_preview_panel()

            if data.get("right_preview"):
                self.local_panel.preview_btn.setChecked(True)
                self.local_panel._toggle_preview_panel()

            # 6. Panel Visibilities
            left_vis = data.get("left_visible", True)
            right_vis = data.get("right_visible", True)
            self.toggle_left_btn.setChecked(left_vis)
            self._toggle_left_panel()
            self.toggle_right_btn.setChecked(right_vis)
            self._toggle_right_panel()

            # 7. Active panel
            active_p = data.get("active_panel", "left")
            self._set_active_panel(active_p)

            # 8. Window geometry & splitter sizes
            geom = data.get("geometry")
            if geom and len(geom) == 4:
                x, y, w, h = geom
                if w > 400 and h > 300:
                    screen = QGuiApplication.primaryScreen()
                    if screen:
                        avail = screen.availableGeometry()
                        w = min(w, avail.width() - 20)
                        h = min(h, avail.height() - 40)
                        x = max(avail.x(), min(x, avail.x() + avail.width() - w))
                        y = max(avail.y() + 35, min(y, avail.y() + avail.height() - h))
                    self.setGeometry(x, y, w, h)
            else:
                self._center_on_screen()

            splitter_sizes = data.get("splitter_sizes")
            if splitter_sizes and len(splitter_sizes) == 3:
                self.splitter.setSizes(splitter_sizes)
                self._user_splitter_sizes = list(splitter_sizes)

        except Exception as e:
            print(f"Error restoring session: {e}")

    def resizeEvent(self, e):
        try:
            super().resizeEvent(e)
        except Exception:
            pass

        try:
            if hasattr(self, "theme_btn") and self.theme_btn:
                mode_icon = "☀️" if CURRENT_THEME_MODE == "dark" else "🌙"
                self.theme_btn.setText(mode_icon)

            if hasattr(self, "splitter") and self.splitter is not None:
                self._update_splitter_sizes()
        except Exception:
            pass

    def showEvent(self, e):
        try:
            super().showEvent(e)
        except Exception:
            pass
        # Ensure middle panel is always aligned symmetrically under Refresh button on startup
        try:
            QTimer.singleShot(0, self._update_splitter_sizes)
        except Exception:
            pass

    def keyPressEvent(self, e):
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, QLineEdit):
            super().keyPressEvent(e)
            return

        if e.key() in (Qt.Key_Left, Qt.Key_Right):
            active_p = self.iphone_panel if self.active_panel == "left" else self.local_panel
            if hasattr(active_p, "video_player") and active_p.video_player.isVisible() and active_p.video_player.player.playbackState() == QMediaPlayer.PlayingState:
                offset = -5000 if e.key() == Qt.Key_Left else 5000
                active_p.video_player.seek_relative(offset)
            else:
                if e.key() == Qt.Key_Left:
                    active_p.select_prev_item()
                else:
                    active_p.select_next_item()
            e.accept()
            return

        # Gjuro Mode WASD navigation: W/S = up/down items, A = back folder, D = forward folder
        if getattr(self, '_gjuro_mode_enabled', False):
            active_p = self.iphone_panel if self.active_panel == "left" else self.local_panel
            if e.key() == Qt.Key_W:
                active_p.select_prev_item()
                e.accept()
                return

            if e.key() == Qt.Key_S:
                active_p.select_next_item()
                e.accept()
                return

            if e.key() == Qt.Key_A:
                self._go_back_active()
                e.accept()
                return

            if e.key() in (Qt.Key_D, Qt.Key_Return, Qt.Key_Enter):
                self._go_forward_active()
                e.accept()
                return

        if e.key() == Qt.Key_Tab:
            self._toggle_active_panel()
            e.accept()
        elif e.key() == Qt.Key_F7:
            self._create_new_folder()
            e.accept()
        elif e.key() == Qt.Key_Space:
            self._preview_active_selection(self.active_panel)
            e.accept()
        else:
            super().keyPressEvent(e)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.KeyPress, QEvent.Enter):
            self.reset_idle_timer()

        if event.type() == QEvent.Enter:
            alt_text = watched.property("robot_alt_text") if hasattr(watched, "property") else None
            if alt_text and getattr(self, '_robot_tips_enabled', True):
                if hasattr(self, "speech_bubble") and self.speech_bubble.isVisible():
                    self.speech_bubble.setText(alt_text)
                    self.speech_bubble.setToolTip(alt_text)
                if hasattr(self, "robot_widget") and self.robot_widget.isVisible():
                    self.robot_widget.trigger_blink()
        elif event.type() == QEvent.Leave:
            if hasattr(watched, "property") and watched.property("robot_alt_text"):
                if getattr(self, '_robot_tips_enabled', True):
                    self._update_active_status_text()
        elif event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            if hasattr(self, "robot_widget") and getattr(self, '_robot_tips_enabled', True) and self.robot_widget.isVisible():
                self.robot_widget.trigger_blink()

        if event.type() == QEvent.KeyPress:
            if QApplication.activeModalWidget() is not None:
                return super().eventFilter(watched, event)

            focused_widget = QApplication.focusWidget()
            if not isinstance(focused_widget, (QLineEdit, QTextEdit)):
                # If focus is inside local_panel or iphone_panel, ensure active_panel matches
                if focused_widget:
                    if hasattr(self, "iphone_panel") and self.iphone_panel.isAncestorOf(focused_widget):
                        self._set_active_panel("left")
                    elif hasattr(self, "local_panel") and self.local_panel.isAncestorOf(focused_widget):
                        self._set_active_panel("right")

                # Spacebar preview
                if event.key() == Qt.Key_Space:
                    self._preview_active_selection(self.active_panel)
                    return True

                # Tab to switch active panel
                if event.key() == Qt.Key_Tab:
                    self._toggle_active_panel()
                    return True

                # Gjuro / Djuro Mode WASD navigation (works in both list & grid modes)
                if getattr(self, '_gjuro_mode_enabled', False):
                    active_p = self.iphone_panel if self.active_panel == "left" else self.local_panel
                    if event.key() == Qt.Key_W:
                        active_p.select_prev_item()
                        return True
                    elif event.key() == Qt.Key_S:
                        active_p.select_next_item()
                        return True
                    elif event.key() == Qt.Key_A:
                        self._go_back_active()
                        return True
                    elif event.key() in (Qt.Key_D, Qt.Key_Return, Qt.Key_Enter):
                        self._go_forward_active()
                        return True
        return super().eventFilter(watched, event)

    def select_file_in_active_panel(self, path_or_file):
        panel = getattr(self, "active_panel_widget", self.iphone_panel)
        if hasattr(panel, "select_path"):
            panel.select_path(path_or_file)

    def open_dark_quicklook(self, panel, target_file_or_path):
        all_items = [path for path, is_folder in panel._all_items if not is_folder and path != ".."]
        
        target_path = target_file_or_path
        if hasattr(target_file_or_path, "path"):
            target_path = target_file_or_path.path
        elif hasattr(target_file_or_path, "name"):
            try:
                target_path = target_file_or_path.name()
            except Exception:
                target_path = str(target_file_or_path)
            
        if not all_items:
            all_items = [target_path]
            
        start_idx = 0
        for i, item in enumerate(all_items):
            item_path = item if isinstance(item, str) else (item.path if hasattr(item, "path") else getattr(item, "name", lambda: str(item))())
            if item_path == target_path or os.path.basename(str(item_path)) == os.path.basename(str(target_path)):
                start_idx = i
                break
                
        dlg = DarkQuickLookDialog(all_items, start_index=start_idx, parent=self)
        dlg.exec()

    def _preview_active_selection(self, panel_name):
        panel = self.iphone_panel if panel_name == "left" else self.local_panel
        selected_items = panel.get_selected()
        all_items = [path for path, is_folder in panel._all_items if not is_folder and path != ".."]
        
        if not all_items and selected_items:
            all_items = selected_items
            
        if selected_items:
            first = selected_items[0]
            start_idx = all_items.index(first) if first in all_items else 0
            
            dlg = DarkQuickLookDialog(all_items, start_index=start_idx, parent=self)
            dlg.exec()

    def _open_in_quick_look(self, path):
        if platform.system() == "Darwin":
            try:
                subprocess.Popen(["qlmanage", "-p", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception as e:
                print(f"Error opening Quick Look: {e}")
        return False

    def _open_preview_local_path(self, path):
        if not path or not os.path.exists(path):
            return
        if os.path.isdir(path):
            self.local_panel.navigate_to_path(path)
            return

        if not self._open_in_quick_look(path):
            try:
                if HAS_PYOBJC:
                    from AppKit import NSWorkspace
                    ws = NSWorkspace.sharedWorkspace()
                    if ws and ws.openFile_(path):
                        return
            except Exception as e:
                print(f"NSWorkspace openFile error: {e}")
            
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            except Exception as e:
                print(f"QDesktopServices error: {e}")
                try:
                    subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass

    def _preview_active_selection(self, panel_name):
        if panel_name == "left":
            files = self.iphone_panel.get_selected()
            if files:
                first = files[0]
                if self.iphone_panel.mode == "local":
                    self._open_preview_local_path(first)
                else:
                    self._open_preview_file(first)
        else:
            paths = self.local_panel.get_selected()
            if paths:
                self._open_preview_local_path(paths[0])

    def _update_pulse_glow(self):
        self.pulse_alpha += self.pulse_direction * 12
        if self.pulse_alpha >= 180:
            self.pulse_alpha = 180
            self.pulse_direction = -1
        elif self.pulse_alpha <= 20:
            self.pulse_alpha = 20
            self.pulse_direction = 1
            
        glow_val = self.pulse_alpha / 255.0
        
        self.iphone_panel.hdr.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(30, 27, 75, 1.0), stop:0.5 rgba(10, 132, 255, {glow_val:.2f}), stop:1 {HEADER});
                border-bottom: 1px solid {BORDER};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
        """)
        self.local_panel.hdr.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(43, 43, 43, 1.0), stop:0.5 rgba(10, 132, 255, {glow_val:.2f}), stop:1 {HEADER});
                border-bottom: 1px solid {BORDER};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
        """)

    def _init_manager(self):
        if HAS_PYOBJC:
            self.manager = ImageCaptureManager()
            self.manager.device_found_signal.connect(self._on_device_found, Qt.QueuedConnection)
            self.manager.device_removed_signal.connect(self._on_device_removed, Qt.QueuedConnection)
            self.manager.items_added_signal.connect(self._on_items_added, Qt.QueuedConnection)
            self.manager.session_opened_signal.connect(self._on_session_opened, Qt.QueuedConnection)
            self.manager.session_closed_signal.connect(self._on_session_closed, Qt.QueuedConnection)
            self.manager.device_ready_signal.connect(self._on_device_ready, Qt.QueuedConnection)
            self.manager.file_downloaded_signal.connect(self._on_file_downloaded, Qt.QueuedConnection)
            self.status_msg.setText("Ready. Local files loaded.")
        else:
            self.manager = None
            self.status_msg.setText("Ready. Local files loaded.")
            if platform.system() == "Windows":
                self._start_device_scanning()

    def _start_device_scanning(self):
        if HAS_PYOBJC and self.manager:
            self.status_msg.setText("Scanning for USB connected iOS devices...")
            self.iphone_panel.update_devices([])
            self.active_devices.clear()
            self.manager.stop_scanning()
            self.manager.start_scanning()
        elif platform.system() == "Windows":
            self.status_msg.setText("Scanning for connected Apple iPhone on Windows USB…")
            self.iphone_panel.update_devices(["🔍 Scanning for Apple iPhone…"])
            self._wpd_worker = WindowsWPDScanWorker(parent=self)
            self._wpd_worker.scan_complete.connect(self._on_windows_wpd_scan_complete)
            self._wpd_worker.scan_error.connect(self._on_windows_wpd_scan_error)
            self._wpd_worker.start()
        else:
            self.status_msg.setText("No USB camera framework available.")
            self.iphone_panel.update_devices(["📱 No iPhone detected"])

    def _on_windows_wpd_scan_complete(self, device_name, wpd_files):
        if wpd_files:
            dev_label = f"📱 {device_name}" if device_name else "📱 Apple iPhone"
            self.iphone_panel.update_devices([dev_label], 0)
            self.iphone_panel.load_files(wpd_files)
            self.status_msg.setText(f"Connected to {dev_label}. Found {len(wpd_files)} media files.")
        else:
            self.iphone_panel.update_devices(["📱 No iPhone detected (Connect via USB & tap Trust)"])
            self.iphone_panel.load_files([])
            self.status_msg.setText("No Apple iPhone detected on USB. Unlock your iPhone, connect via USB cable, and tap 'Trust This Computer'.")

    def _on_windows_wpd_scan_error(self, err_msg):
        print(f"Windows WPD scan error: {err_msg}")
        self.iphone_panel.update_devices(["📱 No iPhone detected"])
        self.iphone_panel.load_files([])
        self.status_msg.setText("Make sure your iPhone is unlocked, connected via USB, and trusted.")

    def _start_android_scanning(self):
        self.iphone_panel.clear()
        adb_path = shutil.which("adb")
        android_devices = []
        android_files = []
        
        if adb_path:
            try:
                res = subprocess.run([adb_path, "devices", "-l"], capture_output=True, text=True, timeout=3)
                lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                for line in lines[1:]:
                    if "device" in line and not line.startswith("*"):
                        parts = line.split()
                        serial = parts[0]
                        model = "Android Device"
                        for p in parts[1:]:
                            if p.startswith("model:"):
                                model = p.split(":")[1].replace("_", " ")
                            elif p.startswith("product:"):
                                if model == "Android Device":
                                    model = p.split(":")[1].replace("_", " ")
                        android_devices.append((serial, model))
            except Exception:
                pass
                
        if android_devices:
            serial, model = android_devices[0]
            dev_name = f"🤖 {model} ({serial})"
            self.iphone_panel.update_devices([dev_name], 0)
            self.status_msg.setText(f"Connected to Android: {model} over USB ADB. Scanning media…")
            
            try:
                ls_cmd = [adb_path, "-s", serial, "shell", "ls -la /sdcard/DCIM/Camera /sdcard/DCIM 2>/dev/null"]
                ls_res = subprocess.run(ls_cmd, capture_output=True, text=True, timeout=5)
                for line in ls_res.stdout.splitlines():
                    match = re.search(r'([-\w]{10})\s+\d+\s+\w+\s+\w+\s+(\d+)\s+[\d-]+\s+[\d:]+\s+(.+)', line)
                    if match:
                        fname = match.group(3).strip()
                        size = int(match.group(2))
                        if any(fname.lower().endswith(ext) for ext in EXTS):
                            remote_path = f"/sdcard/DCIM/Camera/{fname}"
                            android_files.append(AndroidCameraFile(fname, size, remote_path=remote_path, serial=serial))
            except Exception:
                pass
                
            if not android_files:
                self.status_msg.setText(f"Connected to {model}. Catalog is empty.")
            else:
                self.status_msg.setText(f"Loaded Android catalog: {len(android_files)} files found on {model}.")
                
            self.iphone_panel.load_files(android_files)
        else:
            self.status_msg.setText("No Android device detected over USB. Ensure USB Debugging is enabled on your phone.")
            self.iphone_panel.update_devices([])
            self.iphone_panel.load_files([])

    def _toggle_demo_mode(self):
        if not self.demo_mode:
            self.demo_mode = True
            self.status_msg.setText("Running in Simulator/Demo Roll mode.")
            
            fake_files = []
            formats = [("IMG_{:04d}.JPG", 2500000), ("IMG_{:04d}.HEIC", 1500000),
                       ("MOV_{:04d}.MOV", 45000000), ("RAW_{:04d}.DNG", 28000000)]
            for i in range(1, 41):
                fmt, size_base = random.choice(formats)
                name = fmt.format(i)
                size = size_base + random.randint(-50000, 50000)
                fake_files.append(SimulatedCameraFile(name, size))
            
            self.simulated_files = fake_files
            self.iphone_panel.update_devices(["📱 Simulated iPhone 17 Pro Max"], 0)
            self.iphone_panel.load_files(self.simulated_files)
            QTimer.singleShot(300, lambda: self._check_and_prompt_resume(None, self.simulated_files))
        else:
            self.demo_mode = False
            self.iphone_panel.clear()
            self.active_devices.clear()
            
            if HAS_PYOBJC and self.manager:
                self.status_msg.setText("Scanning for USB connected iOS devices...")
                self.iphone_panel.update_devices([])
                self.manager.stop_scanning()
                self.manager.start_scanning()
            else:
                self.status_msg.setText("PyObjC unavailable. Connect option disabled.")
                self.iphone_panel.update_devices(["No USB Framework available"])

    # ── PyObjC Signal Receivers ───────────────────────────────────────────────
    @Slot(object)
    def _on_device_found(self, device):
        if self.demo_mode: return
        if device not in self.active_devices:
            self.active_devices.append(device)
            is_first = len(self.active_devices) == 1
            idx = 0 if is_first else -1
            self.iphone_panel.update_devices(self.active_devices, idx)
            self.status_msg.setText(f"Found connected device: {device.name()}")
            if is_first:
                self._on_device_selected(0)

    @Slot(object)
    def _on_device_removed(self, device):
        if self.demo_mode: return
        if device in self.active_devices:
            self.active_devices.remove(device)
            self.iphone_panel.update_devices(self.active_devices)
            
        if self.current_camera == device:
            if self.downloading_now:
                self._save_interrupted_state()
            self.iphone_panel.clear()
            self.current_camera = None
            self.status_msg.setText("Active device removed.")

    @Slot(int)
    def _on_device_selected(self, index):
        if self.demo_mode: return
        if index < 0 or not self.active_devices:
            self.iphone_panel.clear()
            self.current_camera = None
            return
        device = self.active_devices[index]
        self.iphone_panel.clear()
        self.status_msg.setText(f"Connecting to {device.name()}…")
        self.manager.open_camera_session(device)

    @Slot(object, object)
    def _on_session_opened(self, device, error):
        if self.demo_mode: return
        if error:
            QMessageBox.critical(self, "Connection Error", f"Could not connect: {error.localizedDescription()}")
            self.status_msg.setText("Connection failed.")
            return
        self.current_camera = device
        self.status_msg.setText(f"Connected to {device.name()}. Loading photo catalog…")

    @Slot(object)
    def _on_device_ready(self, device):
        if self.demo_mode: return
        self.status_msg.setText("Loaded camera roll catalog.")
        files = list(device.mediaFiles()) if hasattr(device, "mediaFiles") and device.mediaFiles() else []
        self.iphone_panel.load_files(files)
        if not files:
            self.status_msg.setText(f"Connected to {device.name()}. Catalog is empty. Make sure your iPhone is unlocked and trusted.")
        else:
            self.status_msg.setText(f"Catalog loaded: {len(files)} files found on {device.name()}.")
            QTimer.singleShot(300, lambda: self._check_and_prompt_resume(device, files))

    @Slot(object, object)
    def _on_session_closed(self, device, error):
        if self.demo_mode: return
        self.status_msg.setText("Session closed.")

    @Slot(object)
    def _on_items_added(self, items):
        if self.demo_mode: return
        if self.current_camera:
            files = list(self.current_camera.mediaFiles()) if self.current_camera.mediaFiles() else []
            self.iphone_panel.load_files(files)

    # ── Double Click Preview ──────────────────────────────────────────────────
    def _open_preview(self, card):
        self._open_preview_file(card.file_object)

    def _open_preview_file(self, file_object):
        if self.demo_mode:
            QMessageBox.information(
                self, "Preview (Simulator)",
                f"Simulating Quick Look preview for {file_object.name()}...\n"
                f"File Size: {file_object.fileSize() / (1024*1024):.2f} MB"
            )
            return

        tmp_dir = os.path.join(tempfile.gettempdir(), "image_capture_preview")
        os.makedirs(tmp_dir, exist_ok=True)
        self.status_msg.setText(f"Loading preview for {file_object.name()}…")
        
        class PreviewDelegate(NSObject):
            def initWithParent_path_(self, parent, path):
                self = objc.super(PreviewDelegate, self).init()
                self.parent = parent
                self.path = path
                return self
            def didDownloadFile_error_options_contextInfo_(self, file, error, options, contextInfo):
                self.parent.status_msg.setText("Preview loaded.")
                if not error:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))
                    
        self._preview_delegate = PreviewDelegate.alloc().initWithParent_path_(
            self, os.path.join(tmp_dir, file_object.name())
        )
        dest_url = NSURL.fileURLWithPath_(tmp_dir)
        options = {
            ICDownloadsDirectoryURL: dest_url,
            ICOverwrite: True
        }
        self.current_camera.requestDownloadFile_options_downloadDelegate_didDownloadSelector_contextInfo_(
            file_object,
            options,
            self._preview_delegate,
            "didDownloadFile:error:options:contextInfo:",
            None
        )

    # ── Total Commander Style Actions ─────────────────────────────────────────
    def _create_new_folder(self):
        text, ok = QInputDialog.getText(
            self, "New Folder", "Enter name for new directory:"
        )
        if ok and text:
            target_dir = os.path.join(self.local_panel.current_path, text)
            try:
                os.makedirs(target_dir, exist_ok=True)
                self.status_msg.setText(f"Created folder: {text}")
                self.local_panel.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create folder:\n{e}")

    def _create_screenshots_folder(self):
        target_dir = self.local_panel.current_path
        if os.path.exists(target_dir) and os.path.isdir(target_dir):
            ss_dir = os.path.join(target_dir, "iPhone Screenshots")
            os.makedirs(ss_dir, exist_ok=True)
            if hasattr(self, "speech_bubble"):
                self.speech_bubble.setText("Created 'iPhone Screenshots' folder in local panel.")
            self.local_panel.refresh()

    def _toggle_iphone_commands(self):
        is_hidden = self.iphone_container.isHidden()
        self.iphone_container.setVisible(is_hidden)
        self.iphone_cmd_btn.setText("📱 Commands ▲" if is_hidden else "📱 Commands ▼")

    def _toggle_special_commands(self):
        is_hidden = self.special_container.isHidden()
        self.special_container.setVisible(is_hidden)
        self.special_cmd_btn.setText("✨ Special Commands ▲" if is_hidden else "✨ Special Commands ▼")

    def _delete_selected_local(self):
        selected_paths = self.local_panel.get_selected()
        if not selected_paths:
            QMessageBox.information(self, "Nothing Selected", "Select items in the local panel on the right to delete.")
            return

        confirm = ask_user_confirmation(
            self, "Confirm Delete",
            f"Are you sure you want to permanently delete the {len(selected_paths)} selected item(s)?"
        )
        if confirm == QMessageBox.Yes:
            deleted_count = 0
            for path in selected_paths:
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.unlink(path)
                    deleted_count += 1
                except Exception as e:
                    QMessageBox.warning(self, "Error Deleting", f"Could not delete {Path(path).name}:\n{e}")
            self.status_msg.setText(f"Deleted {deleted_count} items.")
            self.local_panel.refresh()

    def _select_all_active(self):
        if self.active_panel == "left":
            self.iphone_panel.select_all()
        else:
            self.local_panel.select_all()

    def _deselect_all_active(self):
        if self.active_panel == "left":
            self.iphone_panel.deselect_all()
        else:
            self.local_panel.deselect_all()

    # ── Dropdown Menu Actions with Selection Verification ──────────────────────
    def _handle_copy_to_location_action(self):
        files = self.iphone_panel.get_selected()
        if not files:
            if hasattr(self, "speech_bubble"):
                self.speech_bubble.setText("⚠️ Please select files first to copy!")
            if hasattr(self, "robot_widget"):
                self.robot_widget.look_towards(0, 3, happy=False)
            QMessageBox.information(
                self,
                "Select Files First",
                "Please select files first to copy.\n\n"
                "Tip: Click photos or files in the Source panel on the left (or click 'Select All') before choosing Copy to Location."
            )
            return
        self.download_selected_to_destination()

    def _handle_compare_copy_action(self):
        self._compare_and_copy_to_mac()

    # ── Download Operations ───────────────────────────────────────────────────
    def download_selected_to_destination(self):
        if self.active_panel == "right":
            QMessageBox.information(
                self, "Copy Direction",
                "Apple iOS camera rolls are read-only.\n\n"
                "Please select photos in the iPhone panel on the left and copy them to the local folder."
            )
            return

        files = self.iphone_panel.get_selected()
        if not files:
            QMessageBox.information(self, "Nothing selected", "No files to copy from the iPhone panel.")
            return
        if not self.local_panel.current_path:
            QMessageBox.warning(self, "No destination", "Please select a local destination folder first.")
            return
            
        self._start_download_queue(files)

    def _start_download_queue(self, file_list, custom_dest=None):
        if self.downloading_now:
            QMessageBox.warning(self, "Busy", "A transfer is already in progress.")
            return
        
        self.active_download_dest = custom_dest if custom_dest else self.local_panel.current_path
        self.download_queue = list(file_list)
        self.total_downloads = len(self.download_queue)
        self.download_count = 0
        self.downloading_now = True
        self.transfer_paused = False
        self.overwrite_policy = "ask"
        
        # Calculate total transfer size for circular progress
        self.transfer_total_bytes = 0
        for f in file_list:
            try:
                if hasattr(f, "fileSize") and f.fileSize():
                    self.transfer_total_bytes += f.fileSize()
            except Exception:
                pass
        self.transfer_done_bytes = 0
        self.transfer_start_time = time.time()
        
        self.progress.setMaximum(self.total_downloads)
        self.progress.setValue(0)
        self.progress.show()
        self._set_copy_buttons_enabled(False)
        
        # Activate circular progress ring and transfer controls
        if hasattr(self, "circular_progress"):
            self.circular_progress.set_transfer_info(0, self.transfer_total_bytes, 0, self.total_downloads)
            self.circular_progress.set_active(True)
        if hasattr(self, "transfer_controls"):
            self.transfer_controls.set_active(True)
            self.transfer_controls.set_paused(False)
        if hasattr(self, "eta_label"):
            self.eta_label.setText("⏱ Calculating ETA...")
            self.eta_label.show()
        
        # Grid visual copy markers
        for file_obj in self.download_queue:
            for card in self.iphone_panel._cards:
                if hasattr(card, "file_object") and card.file_object == file_obj:
                    if hasattr(card, "set_downloaded"):
                        card.set_downloaded("copying")
                    break
        
        self._process_next_download()

    def _process_next_download(self):
        if not self.download_queue:
            self._finish_downloads()
            return
            
        file_obj = self.download_queue.pop(0)
        
        # Check overwrite policy if file exists
        dest_filepath = os.path.join(self.active_download_dest, file_obj.name())
        if os.path.exists(dest_filepath):
            if self.overwrite_policy == "skip_all":
                self._skip_file(file_obj)
                return
            elif self.overwrite_policy == "ask":
                choice = self._prompt_overwrite(file_obj.name())
                if choice == "overwrite_all":
                    self.overwrite_policy = "overwrite_all"
                elif choice == "skip_all":
                    self.overwrite_policy = "skip_all"
                    self._skip_file(file_obj)
                    return
                elif choice == "skip":
                    self._skip_file(file_obj)
                    return
                # If "overwrite", proceed
                
        self.status_msg.setText(f"Copying {self.download_count + 1}/{self.total_downloads} — {file_obj.name()}…")
        
        is_android = (getattr(self.iphone_panel, "mode", "") == "android")
        is_wpd = isinstance(file_obj, WindowsWPDCameraFile) or getattr(file_obj, "device_name", None)
        is_sim = self.demo_mode or getattr(file_obj, "is_simulated", False) or (is_android and not getattr(file_obj, "remote_path", None))

        if is_sim:
            QTimer.singleShot(400, lambda: self._on_simulated_download_complete(file_obj))
        elif is_wpd:
            self._download_windows_wpd_file(file_obj)
        elif getattr(file_obj, "remote_path", None) and getattr(file_obj, "serial", None):
            self._download_android_file_adb(file_obj)
        elif HAS_PYOBJC and self.manager:
            self.manager.download_file(file_obj, self.active_download_dest)
        else:
            self._download_windows_wpd_file(file_obj)

    def _download_windows_wpd_file(self, file_obj):
        dest_filepath = os.path.join(self.active_download_dest, file_obj.name())
        ps_script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$shell = New-Object -ComObject Shell.Application
$thisPC = $shell.NameSpace(17)
$dev = $null
if ($thisPC) {{
    foreach ($item in $thisPC.Items()) {{
        if ($item.Name -match "iPhone|Apple|iPad|Portable|Camera") {{
            $dev = $item
            break
        }}
    }}
}}
if (-not $dev) {{ exit 1 }}
$destFolder = $shell.NameSpace('{self.active_download_dest.replace("'", "''")}')
if (-not $destFolder) {{ exit 1 }}

function Copy-ItemRecursive($folder, $depth) {{
    if ($depth -gt 6) {{ return $false }}
    $items = $folder.Items()
    if (-not $items) {{ return $false }}
    foreach ($it in $items) {{
        if ($it.IsFolder) {{
            if (Copy-ItemRecursive $it.GetFolder ($depth + 1)) {{ return $true }}
        }} elseif ($it.Name -eq '{file_obj.name().replace("'", "''")}') {{
            $destFolder.CopyHere($it, 20)
            return $true
        }}
    }}
    return $false
}}

$res = Copy-ItemRecursive $dev.GetFolder 0
if ($res) {{ exit 0 }} else {{ exit 1 }}
"""
        try:
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except Exception as e:
            print(f"Error copying WPD file: {e}")
        self._on_file_downloaded(file_obj.name(), None)

    def _download_android_file_adb(self, file_obj):
        adb_path = shutil.which("adb")
        dest_filepath = os.path.join(self.active_download_dest, file_obj.name())
        if adb_path and getattr(file_obj, "serial", None) and getattr(file_obj, "remote_path", None):
            try:
                subprocess.run([adb_path, "-s", file_obj.serial, "pull", file_obj.remote_path, dest_filepath], check=True, capture_output=True)
            except Exception:
                pass
        self._on_file_downloaded(file_obj.name(), None)

    def _on_simulated_download_complete(self, file_object):
        dest_filepath = os.path.join(self.active_download_dest, file_object.name())
        try:
            with open(dest_filepath, "w") as f:
                f.write("Simulated photo content")
        except Exception:
            pass
        self._on_file_downloaded(file_object.name(), None)

    @Slot(str, object)
    def _on_file_downloaded(self, file_name, error_msg):
        self.download_count += 1
        self.progress.setValue(self.download_count)
        
        # Track transferred bytes for circular progress
        file_size = 0
        for card in self.iphone_panel._cards:
            if hasattr(card, "file_object") and hasattr(card.file_object, "name") and card.file_object.name() == file_name:
                try:
                    if hasattr(card.file_object, "fileSize") and card.file_object.fileSize():
                        file_size = card.file_object.fileSize()
                except Exception:
                    pass
                if hasattr(card, "set_downloaded"):
                    card.set_downloaded("done" if error_msg is None else "pending")
                break

        # Fallback: check actual downloaded file size on disk if available
        if file_size == 0 and hasattr(self, "active_download_dest") and self.active_download_dest:
            dest_filepath = os.path.join(self.active_download_dest, file_name)
            if os.path.exists(dest_filepath):
                try:
                    file_size = os.path.getsize(dest_filepath)
                except Exception:
                    pass

        # Second Fallback: estimate average file size if total_bytes was calculated
        if file_size == 0 and getattr(self, "total_downloads", 0) > 0 and getattr(self, "transfer_total_bytes", 0) > 0:
            file_size = self.transfer_total_bytes // self.total_downloads

        self.transfer_done_bytes += file_size
        
        # Update circular progress ring
        if hasattr(self, "circular_progress"):
            self.circular_progress.set_transfer_info(
                self.transfer_done_bytes, self.transfer_total_bytes,
                self.download_count, self.total_downloads
            )

        # Update time remaining ETA label
        self._update_eta_label()
        
        # If paused, don't process next — wait for resume
        if self.transfer_paused:
            return
                
        if self.magic_mode_active:
            self._process_next_magic_download()
        else:
            self._process_next_download()

    def _update_eta_label(self):
        """Calculate and update the time remaining ETA label underneath the circular progress bar."""
        if not hasattr(self, "eta_label") or not hasattr(self, "transfer_start_time"):
            return

        if self.transfer_paused:
            self.eta_label.setText("⏸ Paused")
            self.eta_label.show()
            return

        elapsed = max(0.1, time.time() - self.transfer_start_time)
        eta_sec = 0

        if self.transfer_done_bytes > 0 and self.transfer_total_bytes > 0:
            bps = self.transfer_done_bytes / elapsed
            rem_bytes = max(0, self.transfer_total_bytes - self.transfer_done_bytes)
            eta_sec = rem_bytes / bps if bps > 0 else 0
        elif self.download_count > 0 and self.total_downloads > 0:
            fps = self.download_count / elapsed
            rem_files = max(0, self.total_downloads - self.download_count)
            eta_sec = rem_files / fps if fps > 0 else 0

        if eta_sec > 0:
            m, s = divmod(int(eta_sec), 60)
            if m > 0:
                self.eta_label.setText(f"⏱ {m}m {s:02d}s remaining")
            else:
                self.eta_label.setText(f"⏱ {s}s remaining")
        else:
            self.eta_label.setText("⏱ Almost done...")
        self.eta_label.show()

    def _finish_downloads(self):
        self.downloading_now = False
        self.transfer_paused = False
        self.progress.hide()
        self._set_copy_buttons_enabled(True)
        self.status_msg.setText(f"Copy complete! {self.download_count} files saved to local folder.")
        self.local_panel.refresh()
        self._clear_interrupted_state()
        # Reset circular progress and ETA label
        if hasattr(self, "circular_progress"):
            self.circular_progress.set_transfer_info(
                self.transfer_total_bytes, self.transfer_total_bytes,
                self.download_count, self.total_downloads
            )
            QTimer.singleShot(2000, self.circular_progress.reset)
        if hasattr(self, "eta_label"):
            self.eta_label.setText("✓ Transfer Complete!")
            QTimer.singleShot(2500, self.eta_label.hide)
        if hasattr(self, "transfer_controls"):
            self.transfer_controls.set_active(False)

    def _on_transfer_pause(self):
        """Pause the active file transfer after the current file finishes."""
        if not self.downloading_now or self.transfer_paused:
            return
        self.transfer_paused = True
        if hasattr(self, "circular_progress"):
            self.circular_progress.set_paused(True)
        if hasattr(self, "transfer_controls"):
            self.transfer_controls.set_paused(True)
        if hasattr(self, "eta_label"):
            self.eta_label.setText("⏸ Transfer Paused")
        self.status_msg.setText(f"⏸ Transfer paused — {self.download_count}/{self.total_downloads} files done. Click ▶ to resume.")

    def _on_transfer_continue(self):
        """Resume the paused file transfer from where it stopped."""
        if not self.downloading_now or not self.transfer_paused:
            return
        self.transfer_paused = False
        if hasattr(self, "circular_progress"):
            self.circular_progress.set_paused(False)
        if hasattr(self, "transfer_controls"):
            self.transfer_controls.set_paused(False)
        if hasattr(self, "eta_label"):
            self.eta_label.setText("⏱ Resuming...")
        self.status_msg.setText(f"▶ Resuming transfer — {self.download_count}/{self.total_downloads} files done…")
        # Resume processing the queue
        if self.magic_mode_active:
            self._process_next_magic_download()
        else:
            self._process_next_download()

    def _on_transfer_stop(self):
        """Stop and cancel the entire file transfer, clearing the queue."""
        if not self.downloading_now:
            return
        # Clear the remaining queue
        remaining = len(self.download_queue)
        self.download_queue.clear()
        self.transfer_paused = False
        self.downloading_now = False
        self.magic_mode_active = False
        self.progress.hide()
        self._set_copy_buttons_enabled(True)
        self.pulse_timer.stop()
        self.status_msg.setText(f"⏹ Transfer stopped — {self.download_count} files completed, {remaining} cancelled.")
        # Reset circular progress and ETA label
        if hasattr(self, "circular_progress"):
            self.circular_progress.set_paused(False)
            QTimer.singleShot(1500, self.circular_progress.reset)
        if hasattr(self, "eta_label"):
            self.eta_label.hide()
        if hasattr(self, "transfer_controls"):
            self.transfer_controls.set_active(False)
        self.local_panel.refresh()
        self._clear_interrupted_state()

    def _magic_time_management(self):
        # Determine which panel is active
        if self.active_panel == "left":
            if not self.iphone_panel.has_selection():
                confirm = QMessageBox.question(
                    self, "Magic Folders",
                    "No files selected in the left panel. Do you want to copy and organize ALL files from the left panel?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if confirm == QMessageBox.Yes:
                    files = self.iphone_panel.get_selected()
                else:
                    return
            else:
                files = self.iphone_panel.get_selected()
            
            if not files:
                QMessageBox.information(self, "No files", "No files available to copy.")
                return

            self._start_magic_download_queue(files)
        else:
            # Local file organize mode
            selected_paths = self.local_panel.get_selected()
            if not selected_paths:
                confirm = QMessageBox.question(
                    self, "Magic Folders",
                    "No files selected in the right panel. Do you want to organize ALL files in the current folder?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if confirm == QMessageBox.Yes:
                    selected_paths = [path for path, is_folder in self.local_panel._all_items if not is_folder and path != ".."]
                else:
                    return

            if not selected_paths:
                QMessageBox.information(self, "No files", "No files to organize in the current local folder.")
                return

            self._organize_local_files_by_date(selected_paths)

    def _start_magic_download_queue(self, file_list):
        if self.downloading_now:
            QMessageBox.warning(self, "Busy", "A transfer is already in progress.")
            return
        
        self.download_queue = []
        for file_obj in file_list:
            folder_name = "unknown"
            # If file_obj is a path (local) or file object (iphone)
            if isinstance(file_obj, str):
                name = os.path.basename(file_obj)
                try:
                    mtime = os.path.getmtime(file_obj)
                    dt = datetime.fromtimestamp(mtime)
                    folder_name = dt.strftime("%Y-%m")
                except Exception:
                    pass
            else:
                name = file_obj.name()
                if hasattr(file_obj, "creationDate") and file_obj.creationDate():
                    try:
                        date_str = str(file_obj.creationDate())
                        if len(date_str) >= 7 and date_str[4] == '-':
                            year = date_str[:4]
                            month = date_str[5:7]
                            folder_name = f"{year}-{month}"
                    except Exception:
                        pass
            
            dest_dir = os.path.join(self.local_panel.current_path, folder_name)
            self.download_queue.append((file_obj, dest_dir))
            
        self.total_downloads = len(self.download_queue)
        self.download_count = 0
        self.downloading_now = True
        self.magic_mode_active = True
        self.transfer_paused = False
        self.overwrite_policy = "ask"
        
        # Calculate total transfer size for circular progress
        self.transfer_total_bytes = 0
        for item, _ in self.download_queue:
            try:
                if hasattr(item, "fileSize") and item.fileSize():
                    self.transfer_total_bytes += item.fileSize()
                elif isinstance(item, str) and os.path.isfile(item):
                    self.transfer_total_bytes += os.path.getsize(item)
            except Exception:
                pass
        self.transfer_done_bytes = 0
        self.transfer_start_time = time.time()
        
        self.progress.setMaximum(self.total_downloads)
        self.progress.setValue(0)
        self.progress.show()
        self._set_copy_buttons_enabled(False)
        self.pulse_timer.start()
        
        # Activate circular progress ring and transfer controls
        if hasattr(self, "circular_progress"):
            self.circular_progress.set_transfer_info(0, self.transfer_total_bytes, 0, self.total_downloads)
            self.circular_progress.set_active(True)
        if hasattr(self, "transfer_controls"):
            self.transfer_controls.set_active(True)
            self.transfer_controls.set_paused(False)
        if hasattr(self, "eta_label"):
            self.eta_label.setText("⏱ Calculating ETA...")
            self.eta_label.show()
        
        # Grid visual copy markers
        for item, _ in self.download_queue:
            for card in self.iphone_panel._cards:
                if (hasattr(card, "file_object") and card.file_object == item) or (hasattr(card, "path") and card.path == item):
                    if hasattr(card, "set_downloaded"):
                        card.set_downloaded("copying")
                    break
        
        self._process_next_magic_download()

    def _process_next_magic_download(self):
        if not self.download_queue:
            self._finish_magic_downloads()
            return
            
        file_obj, dest_dir = self.download_queue.pop(0)
        name = os.path.basename(file_obj) if isinstance(file_obj, str) else file_obj.name()
        
        # Check overwrite policy if file exists
        dest_filepath = os.path.join(dest_dir, name)
        if os.path.exists(dest_filepath):
            if self.overwrite_policy == "skip_all":
                self._skip_file(file_obj)
                return
            elif self.overwrite_policy == "ask":
                choice = self._prompt_overwrite(name)
                if choice == "overwrite_all":
                    self.overwrite_policy = "overwrite_all"
                elif choice == "skip_all":
                    self.overwrite_policy = "skip_all"
                    self._skip_file(file_obj)
                    return
                elif choice == "skip":
                    self._skip_file(file_obj)
                    return
                # If "overwrite", proceed
                
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception:
            pass
        
        self.status_msg.setText(f"Magic Copying {self.download_count + 1}/{self.total_downloads} — {name} to {os.path.basename(dest_dir)}…")
        
        if self.demo_mode or isinstance(file_obj, str):
            # In demo mode or if local file, process copy/move simulation or action directly
            if isinstance(file_obj, str):
                try:
                    shutil.copy2(file_obj, dest_filepath)
                except Exception:
                    pass
            QTimer.singleShot(400, lambda: self._on_simulated_magic_download_complete(file_obj, dest_dir))
        else:
            self.manager.download_file(file_obj, dest_dir)

    def _on_simulated_magic_download_complete(self, file_object, dest_dir):
        if not isinstance(file_object, str):
            dest_filepath = os.path.join(dest_dir, file_object.name())
            try:
                with open(dest_filepath, "w") as f:
                    f.write("Simulated photo content")
            except Exception:
                pass
        name = file_object if isinstance(file_object, str) else file_object.name()
        self._on_file_downloaded(name, None)

    def _finish_magic_downloads(self):
        self.downloading_now = False
        self.magic_mode_active = False
        self.transfer_paused = False
        self.progress.hide()
        self._set_copy_buttons_enabled(True)
        self.pulse_timer.stop()
        self.iphone_panel.hdr.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1e1b4b, stop:1 {HEADER}); border-bottom: 1px solid {BORDER}; border-top-left-radius: 6px; border-top-right-radius: 6px;")
        self.local_panel.hdr.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2b2b2b, stop:1 {HEADER}); border-bottom: 1px solid {BORDER}; border-top-left-radius: 6px; border-top-right-radius: 6px;")
        if getattr(self, "extract_png_active", False):
            self.status_msg.setText("Extract PNG complete! Screenshots saved in 'screenshots' folder.")
            self.extract_png_active = False
        elif getattr(self, "extract_videos_active", False):
            self.status_msg.setText("Extract Videos complete! Video files saved in 'videos' folder.")
            self.extract_videos_active = False
        else:
            self.status_msg.setText("Magic Transfer complete! Organized files saved in monthly subfolders.")
        self.iphone_panel.refresh()
        self.local_panel.refresh()
        self._clear_interrupted_state()
        # Reset circular progress and ETA label to inactive
        if hasattr(self, "circular_progress"):
            self.circular_progress.set_transfer_info(
                self.transfer_total_bytes, self.transfer_total_bytes,
                self.download_count, self.total_downloads
            )
            QTimer.singleShot(2000, self.circular_progress.reset)
        if hasattr(self, "eta_label"):
            self.eta_label.setText("✓ Transfer Complete!")
            QTimer.singleShot(2500, self.eta_label.hide)
        if hasattr(self, "transfer_controls"):
            self.transfer_controls.set_active(False)

    def _organize_local_files_by_date(self, selected_paths):
        moved_count = 0
        for path in selected_paths:
            if not os.path.exists(path) or os.path.isdir(path):
                continue
            
            try:
                mtime = os.path.getmtime(path)
                dt = datetime.fromtimestamp(mtime)
                folder_name = dt.strftime("%Y-%m")
                
                dest_dir = os.path.join(self.local_panel.current_path, folder_name)
                os.makedirs(dest_dir, exist_ok=True)
                
                dest_path = os.path.join(dest_dir, os.path.basename(path))
                if path != dest_path:
                    shutil.move(path, dest_path)
                    moved_count += 1
            except Exception as e:
                print(f"Error organizing {path}: {e}")
                
        self.status_msg.setText(f"Magic Folders complete! Organized {moved_count} files into monthly folders.")
        self.local_panel.refresh()

    def _extract_png(self):
        # Determine active panel selection
        if self.active_panel == "left":
            selected = self.iphone_panel.get_selected()
            is_iphone = (self.iphone_panel.mode == "iphone")
            src_panel = self.iphone_panel
        else:
            selected = self.local_panel.get_selected()
            is_iphone = False
            src_panel = self.local_panel
            
        if not selected:
            QMessageBox.information(
                self, "Extract PNG",
                "Please select files first."
            )
            return
            
        # Filter for .png files (supporting str paths, LocalCard, IPhoneCard, and media objects)
        png_files = []
        for item in selected:
            if isinstance(item, str):
                file_name = os.path.basename(item)
            elif hasattr(item, 'file_name'):
                file_name = item.file_name
            elif hasattr(item, 'path'):
                file_name = os.path.basename(item.path)
            elif hasattr(item, 'name'):
                file_name = item.name() if callable(item.name) else item.name
            else:
                file_name = str(item)

            if file_name.lower().endswith(".png"):
                png_files.append(item)
                
        if not png_files:
            QMessageBox.information(
                self, "Extract PNG",
                "No .png files found in the current selection."
            )
            return
            
        if is_iphone:
            # Download PNGs from iPhone to local panel's screenshots folder
            dest_dir = os.path.join(self.local_panel.current_path, "screenshots")
            os.makedirs(dest_dir, exist_ok=True)
            self._start_extract_png_download_queue(png_files)
        else:
            # Local organization: Move PNG files safely to screenshots subfolder inside current folder
            dest_dir = os.path.join(src_panel.current_path, "screenshots")
            os.makedirs(dest_dir, exist_ok=True)
            
            moved_count = 0
            for item in png_files:
                # Resolve full absolute path for local files
                if isinstance(item, str):
                    abs_path = item if os.path.isabs(item) else os.path.join(src_panel.current_path, item)
                elif hasattr(item, 'path'):
                    p = item.path
                    abs_path = p if os.path.isabs(p) else os.path.join(src_panel.current_path, p)
                else:
                    continue

                if not os.path.exists(abs_path) or os.path.isdir(abs_path):
                    continue

                try:
                    dest_path = os.path.join(dest_dir, os.path.basename(abs_path))
                    if os.path.abspath(abs_path) != os.path.abspath(dest_path):
                        # Copy first to guarantee 100% file safety, verify size, then remove original
                        shutil.copy2(abs_path, dest_path)
                        if os.path.exists(dest_path) and os.path.getsize(dest_path) == os.path.getsize(abs_path):
                            os.remove(abs_path)
                            moved_count += 1
                except Exception as e:
                    print(f"Error extracting PNG file {abs_path}: {e}")
                    
            self.status_msg.setText(f"Extract PNG complete! Organized {moved_count} PNG files into 'screenshots' folder.")
            src_panel.refresh()

    def _extract_videos(self):
        # Determine active panel selection
        if self.active_panel == "left":
            selected = self.iphone_panel.get_selected()
            is_iphone = (self.iphone_panel.mode == "iphone")
            src_panel = self.iphone_panel
        else:
            selected = self.local_panel.get_selected()
            is_iphone = False
            src_panel = self.local_panel
            
        if not selected:
            QMessageBox.information(
                self, "Extract Videos",
                "Please select files first."
            )
            return
            
        # Filter for video files (supporting str paths, LocalCard, IPhoneCard, and media objects)
        video_files = []
        for item in selected:
            if isinstance(item, str):
                file_name = os.path.basename(item)
            elif hasattr(item, 'file_name'):
                file_name = item.file_name
            elif hasattr(item, 'path'):
                file_name = os.path.basename(item.path)
            elif hasattr(item, 'name'):
                file_name = item.name() if callable(item.name) else item.name
            else:
                file_name = str(item)

            ext = os.path.splitext(file_name)[1].lower()
            if ext in VIDEO_EXTS:
                video_files.append(item)
                
        if not video_files:
            QMessageBox.information(
                self, "Extract Videos",
                "No video files (.mp4, .mov, .m4v, .mkv, .avi) found in the current selection."
            )
            return
            
        if is_iphone:
            # Download videos from iPhone to local panel's videos folder
            dest_dir = os.path.join(self.local_panel.current_path, "videos")
            os.makedirs(dest_dir, exist_ok=True)
            self._start_extract_videos_download_queue(video_files)
        else:
            # Local organization: Move video files safely to videos subfolder inside current folder
            dest_dir = os.path.join(src_panel.current_path, "videos")
            os.makedirs(dest_dir, exist_ok=True)
            
            moved_count = 0
            for item in video_files:
                # Resolve full absolute path for local files
                if isinstance(item, str):
                    abs_path = item if os.path.isabs(item) else os.path.join(src_panel.current_path, item)
                elif hasattr(item, 'path'):
                    p = item.path
                    abs_path = p if os.path.isabs(p) else os.path.join(src_panel.current_path, p)
                else:
                    continue

                if not os.path.exists(abs_path) or os.path.isdir(abs_path):
                    continue

                try:
                    dest_path = os.path.join(dest_dir, os.path.basename(abs_path))
                    if os.path.abspath(abs_path) != os.path.abspath(dest_path):
                        # Copy first to guarantee 100% file safety, verify size, then remove original
                        shutil.copy2(abs_path, dest_path)
                        if os.path.exists(dest_path) and os.path.getsize(dest_path) == os.path.getsize(abs_path):
                            os.remove(abs_path)
                            moved_count += 1
                except Exception as e:
                    print(f"Error extracting video file {abs_path}: {e}")
                    
            self.status_msg.setText(f"Extract Videos complete! Organized {moved_count} video files into 'videos' folder.")
            src_panel.refresh()

    def _start_extract_videos_download_queue(self, file_list):
        if self.downloading_now:
            QMessageBox.warning(self, "Busy", "A transfer is already in progress.")
            return
            
        dest_dir = os.path.join(self.local_panel.current_path, "videos")
        self.download_queue = []
        for file_obj in file_list:
            self.download_queue.append((file_obj, dest_dir))
            
        self.total_downloads = len(self.download_queue)
        self.download_count = 0
        self.downloading_now = True
        self.magic_mode_active = True
        self.extract_videos_active = True
        self.overwrite_policy = "ask"
        
        self.progress.setMaximum(self.total_downloads)
        self.progress.setValue(0)
        self.progress.show()
        self._set_copy_buttons_enabled(False)
        self.pulse_timer.start()
        
        # Grid visual copy markers
        for item, _ in self.download_queue:
            for card in self.iphone_panel._cards:
                if (hasattr(card, "file_object") and card.file_object == item) or (hasattr(card, "path") and card.path == item):
                    if hasattr(card, "set_downloaded"):
                        card.set_downloaded("copying")
                    break
                    
        self._process_next_magic_download()

    def _start_extract_png_download_queue(self, file_list):
        if self.downloading_now:
            QMessageBox.warning(self, "Busy", "A transfer is already in progress.")
            return
            
        dest_dir = os.path.join(self.local_panel.current_path, "screenshots")
        self.download_queue = []
        for file_obj in file_list:
            self.download_queue.append((file_obj, dest_dir))
            
        self.total_downloads = len(self.download_queue)
        self.download_count = 0
        self.downloading_now = True
        self.magic_mode_active = True
        self.extract_png_active = True
        self.overwrite_policy = "ask"
        
        self.progress.setMaximum(self.total_downloads)
        self.progress.setValue(0)
        self.progress.show()
        self._set_copy_buttons_enabled(False)
        self.pulse_timer.start()
        
        # Grid visual copy markers
        for item, _ in self.download_queue:
            for card in self.iphone_panel._cards:
                if (hasattr(card, "file_object") and card.file_object == item) or (hasattr(card, "path") and card.path == item):
                    if hasattr(card, "set_downloaded"):
                        card.set_downloaded("copying")
                    break
                    
        self._process_next_magic_download()

    def _prompt_overwrite(self, filename):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("File Already Exists")
        msg_box.setText(f"The file '{filename}' already exists in the destination folder.\nWhat would you like to do?")
        
        markopolo_path = os.path.join(script_dir, "markopolo.png")
        if os.path.exists(markopolo_path):
            pix = QPixmap(markopolo_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            msg_box.setIconPixmap(pix)
        
        overwrite_btn = msg_box.addButton("Overwrite", QMessageBox.YesRole)
        overwrite_all_btn = msg_box.addButton("Overwrite All", QMessageBox.YesRole)
        skip_btn = msg_box.addButton("Skip", QMessageBox.NoRole)
        skip_all_btn = msg_box.addButton("Skip All", QMessageBox.NoRole)
        
        msg_box.exec()
        
        clicked = msg_box.clickedButton()
        if clicked == overwrite_btn:
            return "overwrite"
        elif clicked == overwrite_all_btn:
            return "overwrite_all"
        elif clicked == skip_btn:
            return "skip"
        elif clicked == skip_all_btn:
            return "skip_all"
        return "skip"

    def _skip_file(self, file_object):
        self.download_count += 1
        self.progress.setValue(self.download_count)
        
        for card in self.iphone_panel._cards:
            if hasattr(card, "file_object") and card.file_object == file_object:
                if hasattr(card, "set_downloaded"):
                    card.set_downloaded("pending")
                break
                
        if self.magic_mode_active:
            self._process_next_magic_download()
        else:
            self._process_next_download()

    def _save_interrupted_state(self):
        if not self.downloading_now:
            return
            
        remaining = []
        magic_folders = {}
        
        if self.magic_mode_active:
            for file_obj, dest_dir in self.download_queue:
                name = os.path.basename(file_obj) if isinstance(file_obj, str) else file_obj.name()
                remaining.append(name)
                magic_folders[name] = dest_dir
        else:
            for file_obj in self.download_queue:
                name = os.path.basename(file_obj) if isinstance(file_obj, str) else file_obj.name()
                remaining.append(name)
                
        if not remaining:
            self._clear_interrupted_state()
            return
            
        state = {
            "device_name": self.current_camera.name() if self.current_camera else "Simulated iPhone",
            "destination": self.active_download_dest,
            "magic_mode": self.magic_mode_active,
            "magic_folders": magic_folders,
            "remaining_files": remaining
        }
        
        try:
            state_path = os.path.expanduser("~/.gemini/antigravity-ide/interrupted_transfer.json")
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)
            self.status_msg.setText("Transfer interrupted. Progress saved.")
        except Exception as e:
            print(f"Error saving interrupted state: {e}")

    def _clear_interrupted_state(self):
        state_path = os.path.expanduser("~/.gemini/antigravity-ide/interrupted_transfer.json")
        if os.path.exists(state_path):
            try:
                os.remove(state_path)
            except Exception:
                pass

    def _check_and_prompt_resume(self, device, files):
        state_path = os.path.expanduser("~/.gemini/antigravity-ide/interrupted_transfer.json")
        if not os.path.exists(state_path):
            return
            
        try:
            with open(state_path, "r") as f:
                state = json.load(f)
        except Exception:
            return
            
        expected_device = state.get("device_name", "")
        current_device_name = device.name() if device else "Simulated iPhone"
        
        if expected_device != current_device_name:
            return
            
        remaining_names = state.get("remaining_files", [])
        if not remaining_names:
            self._clear_interrupted_state()
            return
            
        confirm = QMessageBox.question(
            self, "Resume Transfer",
            f"You have an interrupted transfer for '{current_device_name}' with {len(remaining_names)} files remaining.\n"
            f"Would you like to resume copying these files now?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            file_map = {f.name(): f for f in files}
            
            magic_mode = state.get("magic_mode", False)
            magic_folders = state.get("magic_folders", {})
            destination = state.get("destination", self.local_panel.current_path)
            
            queue_items = []
            for name in remaining_names:
                if name in file_map:
                    file_obj = file_map[name]
                    if magic_mode:
                        dest_dir = magic_folders.get(name, destination)
                        queue_items.append((file_obj, dest_dir))
                    else:
                        queue_items.append(file_obj)
            
            if not queue_items:
                QMessageBox.information(self, "No files found", "The remaining files could not be found on the connected device.")
                self._clear_interrupted_state()
                return
                
            if magic_mode:
                self._resume_magic_download_queue(queue_items, destination)
            else:
                self._resume_download_queue(queue_items, destination)
        else:
            self._clear_interrupted_state()

    def _resume_download_queue(self, queue_items, destination):
        self.active_download_dest = destination
        self.download_queue = list(queue_items)
        self.total_downloads = len(self.download_queue)
        self.download_count = 0
        self.downloading_now = True
        self.overwrite_policy = "ask"
        
        self.progress.setMaximum(self.total_downloads)
        self.progress.setValue(0)
        self.progress.show()
        self._set_copy_buttons_enabled(False)
        
        for file_obj in self.download_queue:
            for card in self.iphone_panel._cards:
                if hasattr(card, "file_object") and card.file_object == file_obj:
                    if hasattr(card, "set_downloaded"):
                        card.set_downloaded("copying")
                    break
        
        self._process_next_download()

    def _resume_magic_download_queue(self, queue_items, destination):
        self.download_queue = list(queue_items)
        self.total_downloads = len(self.download_queue)
        self.download_count = 0
        self.downloading_now = True
        self.magic_mode_active = True
        self.overwrite_policy = "ask"
        
        self.progress.setMaximum(self.total_downloads)
        self.progress.setValue(0)
        self.progress.show()
        self._set_copy_buttons_enabled(False)
        
        for file_obj, _ in self.download_queue:
            for card in self.iphone_panel._cards:
                if hasattr(card, "file_object") and card.file_object == file_obj:
                    if hasattr(card, "set_downloaded"):
                        card.set_downloaded("copying")
                    break
                    
        self._process_next_magic_download()

    def _delete_duplicates_local(self):
        current_dir = self.local_panel.current_path
        if not current_dir or not os.path.isdir(current_dir):
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid local directory first.")
            return

        try:
            all_entries = os.listdir(current_dir)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read directory contents:\n{e}")
            return

        # Pattern to match stem ending with a space followed by digits, or digits inside parentheses
        # e.g., "NAME114 1" or "NAME114 (1)"
        dup_pattern = re.compile(r'^(.+?)(?:\s+\d+|\s*\(\d+\))$', re.IGNORECASE)
        
        duplicates_found = []
        existing_files_lower = {entry.lower(): entry for entry in all_entries if os.path.isfile(os.path.join(current_dir, entry))}
        
        for entry in all_entries:
            full_path = os.path.join(current_dir, entry)
            if not os.path.isfile(full_path):
                continue
            if entry.startswith('.'):
                continue
                
            name_part, ext_part = os.path.splitext(entry)
            match = dup_pattern.match(name_part)
            if match:
                original_stem = match.group(1)
                original_filename = original_stem + ext_part
                
                if original_filename.lower() in existing_files_lower:
                    orig_actual_name = existing_files_lower[original_filename.lower()]
                    duplicates_found.append((full_path, orig_actual_name))

        if not duplicates_found:
            QMessageBox.information(self, "No Duplicates Found", "No duplicate files (e.g., 'NAME114 1.jpg' when 'NAME114.jpg' exists) were found in the current folder.")
            return

        list_str = "\n".join([f"• {os.path.basename(dup)} (original: {orig})" for dup, orig in duplicates_found[:15]])
        if len(duplicates_found) > 15:
            list_str += f"\n... and {len(duplicates_found) - 15} more files."
            
        confirm = QMessageBox.question(
            self, "Delete Duplicates",
            f"Found {len(duplicates_found)} duplicate file(s) in the current directory:\n\n{list_str}\n\n"
            f"Are you sure you want to permanently delete these duplicate files?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            deleted_count = 0
            for dup_path, _ in duplicates_found:
                try:
                    os.unlink(dup_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting duplicate {dup_path}: {e}")
            
            self.status_msg.setText(f"Deleted {deleted_count} duplicate files.")
            self.local_panel.refresh()

    def _reverse_time_management(self):
        current_dir = self.local_panel.current_path
        if not current_dir or not os.path.isdir(current_dir):
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid local directory first.")
            return

        try:
            entries = os.listdir(current_dir)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read directory contents:\n{e}")
            return

        date_folder_pattern = re.compile(r'^(\d{4}-\d{2}|\d{2}-\d{4})$')
        target_folders = []
        for entry in entries:
            full_path = os.path.join(current_dir, entry)
            if os.path.isdir(full_path) and date_folder_pattern.match(entry):
                target_folders.append((full_path, entry))

        if not target_folders:
            QMessageBox.information(
                self, "No Date Folders Found",
                "No date subfolders (e.g., '2026-06' or '06-2026') were found in the current directory."
            )
            return

        confirm = QMessageBox.question(
            self, "Confirm Reverse Time Management",
            f"Found {len(target_folders)} date subfolder(s).\n\n"
            f"This will move all files from these subfolders back to the current directory and delete the subfolders if they become empty.\n\n"
            f"Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm != QMessageBox.Yes:
            return

        moved_count = 0
        deleted_folders_count = 0
        self.overwrite_policy = "ask"

        for folder_path, folder_name in target_folders:
            try:
                folder_entries = os.listdir(folder_path)
            except Exception as e:
                print(f"Could not read folder {folder_name}: {e}")
                continue

            for sub_entry in folder_entries:
                sub_entry_path = os.path.join(folder_path, sub_entry)
                if not os.path.isfile(sub_entry_path):
                    continue

                dest_path = os.path.join(current_dir, sub_entry)
                
                if os.path.exists(dest_path):
                    if self.overwrite_policy == "skip_all":
                        continue
                    elif self.overwrite_policy == "ask":
                        choice = self._prompt_overwrite(sub_entry)
                        if choice == "overwrite_all":
                            self.overwrite_policy = "overwrite_all"
                        elif choice == "skip_all":
                            self.overwrite_policy = "skip_all"
                            continue
                        elif choice == "skip":
                            continue

                try:
                    if os.path.exists(dest_path):
                        os.unlink(dest_path)
                    shutil.move(sub_entry_path, dest_path)
                    moved_count += 1
                except Exception as e:
                    print(f"Error moving {sub_entry} from {folder_name}: {e}")

            try:
                remaining_entries = os.listdir(folder_path)
                remaining_files = [r for r in remaining_entries if r != '.DS_Store']
                if not remaining_files:
                    for r in remaining_entries:
                        try:
                            os.unlink(os.path.join(folder_path, r))
                        except Exception:
                            pass
                    os.rmdir(folder_path)
                    deleted_folders_count += 1
            except Exception as e:
                print(f"Error removing folder {folder_name}: {e}")

        self.status_msg.setText(f"Reverse Time Management complete! Moved {moved_count} files and deleted {deleted_folders_count} empty subfolders.")
        self.local_panel.refresh()

    def _set_copy_buttons_enabled(self, enabled):
        if hasattr(self, "copy_btn"):
            self.copy_btn.setEnabled(enabled)
        if hasattr(self, "compare_copy_btn"):
            self.compare_copy_btn.setEnabled(enabled)
        if hasattr(self, "mid_extract_png"):
            self.mid_extract_png.setEnabled(enabled)
        if hasattr(self, "mid_magic"):
            self.mid_magic.setEnabled(enabled)
        if hasattr(self, "mid_undo_magic"):
            self.mid_undo_magic.setEnabled(enabled)
        if hasattr(self, "mid_back") and hasattr(self, "mid_fwd"):
            if enabled:
                self._update_middle_nav_buttons()
            else:
                self.mid_back.setEnabled(False)
                self.mid_fwd.setEnabled(False)

    def _compare_and_copy_to_mac(self):
        # If there are selected files, only compare/copy the selection. Otherwise, compare/copy all loaded/filtered files.
        if self.iphone_panel.has_selection():
            iphone_files = self.iphone_panel.get_selected()
        else:
            iphone_files = self.iphone_panel._filtered_files()
            
        if not iphone_files:
            QMessageBox.information(
                self, "No Files",
                "There are no files loaded in the iPhone panel on the left to copy."
            )
            return

        dest_dir = self.local_panel.current_path
        if not dest_dir or not os.path.isdir(dest_dir):
            QMessageBox.warning(
                self, "No Destination",
                "Please select a valid local destination folder on the right panel first."
            )
            return

        self.status_msg.setText("Comparing files between iPhone and local directory…")
        QApplication.processEvents()

        local_filenames = set()
        try:
            for root, dirs, files in os.walk(dest_dir):
                for file in files:
                    if not file.startswith('.'):
                        local_filenames.add(file.lower())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not scan local destination directory:\n{e}")
            self.status_msg.setText("Comparison failed.")
            return

        to_copy = []
        for file_obj in iphone_files:
            name = file_obj.name()
            if name.lower() not in local_filenames:
                to_copy.append(file_obj)

        # Build Compare & Copy Options popup window with explicit copy action buttons
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Compare & Copy Options")

        markopolo_path = os.path.join(script_dir, "markopolo.png")
        if os.path.exists(markopolo_path):
            pix = QPixmap(markopolo_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            msg_box.setIconPixmap(pix)

        total_scanned = len(iphone_files)
        missing_count = len(to_copy)
        existing_count = total_scanned - missing_count

        if missing_count > 0:
            msg_box.setText(
                f"Comparison Results:\n\n"
                f"• {missing_count} missing file(s) found on Source panel.\n"
                f"• {existing_count} file(s) already exist in destination folder.\n\n"
                f"Select an option to proceed with copying:"
            )
            btn_missing = msg_box.addButton(f"Copy Missing Files ({missing_count})", QMessageBox.AcceptRole)
            btn_all = msg_box.addButton(f"Copy All Files ({total_scanned})", QMessageBox.YesRole)
            btn_cancel = msg_box.addButton("Cancel", QMessageBox.RejectRole)
            msg_box.setDefaultButton(btn_missing)
        else:
            msg_box.setText(
                f"Comparison Results:\n\n"
                f"• All {total_scanned} file(s) are already present in the destination directory.\n\n"
                f"Would you like to copy/overwrite all files anyway?"
            )
            btn_missing = None
            btn_all = msg_box.addButton(f"Copy All Files ({total_scanned})", QMessageBox.YesRole)
            btn_cancel = msg_box.addButton("Cancel", QMessageBox.RejectRole)
            msg_box.setDefaultButton(btn_all)

        msg_box.exec()
        clicked = msg_box.clickedButton()

        if btn_missing and clicked == btn_missing:
            self.overwrite_policy = "ask"
            self._start_download_queue(to_copy)
        elif clicked == btn_all:
            self.overwrite_policy = "ask"
            self._start_download_queue(iphone_files)
        else:
            self.status_msg.setText("Compare & copy canceled.")

    def _refresh_both(self):
        if self.demo_mode:
            self.demo_mode = False
            self._toggle_demo_mode()
        else:
            self.status_msg.setText("Rescanning connected USB devices...")
            if hasattr(self, "_start_device_scanning"):
                self._start_device_scanning()
            if self.current_camera:
                self.manager.close_camera_session()
                self.manager.open_camera_session(self.current_camera)
        self.local_panel.refresh()

    def closeEvent(self, e):
        box = QMessageBox(self)
        box.setWindowTitle(f"Quit Marko Polo Explorer v{__version__}")
        box.setText(f"Are you sure you want to quit Marko Polo Explorer v{__version__}?")
        box.setInformativeText("💾 Save & Quit: Saves current paths, layout, and settings options for next launch.\n⚡ Quit Without Saving: Exits without saving session state.")
        
        markopolo_path = os.path.join(script_dir, "markopolo.png")
        if os.path.exists(markopolo_path):
            pix = QPixmap(markopolo_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            box.setIconPixmap(pix)
        
        save_btn = box.addButton("💾 Save & Quit", QMessageBox.AcceptRole)
        nosave_btn = box.addButton("Don't Save", QMessageBox.DestructiveRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.RejectRole)
        
        box.setDefaultButton(save_btn)

        box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {PANEL_BG};
                color: {TEXT};
            }}
            QLabel {{
                color: {TEXT};
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton {{
                background-color: {BTN_BG};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 13px;
                min-width: 105px;
            }}
            QPushButton:hover {{
                background-color: {BTN_HOVER};
            }}
            QPushButton:default {{
                background-color: {ACCENT};
                color: white;
                border: 1px solid {ACCENT};
                font-weight: bold;
            }}
            QPushButton:default:hover {{
                background-color: {ACCENT2};
                color: black;
            }}
        """)

        box.exec()
        clicked = box.clickedButton()
        if clicked == save_btn:
            try:
                self._save_session()
            except Exception:
                pass
            if self.downloading_now:
                try:
                    self._save_interrupted_state()
                except Exception:
                    pass
            if hasattr(self, "manager") and self.manager:
                try:
                    self.manager.stop_scanning()
                except Exception:
                    pass
            try:
                if hasattr(self, "idle_timer") and self.idle_timer:
                    self.idle_timer.stop()
                if hasattr(self, "movie_timer") and self.movie_timer:
                    self.movie_timer.stop()
                QThreadPool.globalInstance().clear()
                QThreadPool.globalInstance().waitForDone(100)
            except Exception:
                pass
            
            e.accept()
            QApplication.quit()
            os._exit(0)
        elif clicked == nosave_btn:
            session_file = os.path.join(script_dir, "marko_polo_session.json")
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except Exception:
                    pass
            if hasattr(self, "manager") and self.manager:
                try:
                    self.manager.stop_scanning()
                except Exception:
                    pass
            try:
                if hasattr(self, "idle_timer") and self.idle_timer:
                    self.idle_timer.stop()
                if hasattr(self, "movie_timer") and self.movie_timer:
                    self.movie_timer.stop()
                QThreadPool.globalInstance().clear()
                QThreadPool.globalInstance().waitForDone(100)
            except Exception:
                pass
            
            e.accept()
            QApplication.quit()
            os._exit(0)
        else:
            e.ignore()


def main():
    if HAS_PYOBJC:
        try:
            bundle = NSBundle.mainBundle()
            if bundle:
                app_info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                if app_info is not None:
                    app_info['CFBundleName'] = "Marko Polo Explorer"
                    app_info['CFBundleDisplayName'] = f"Marko Polo Explorer v{__version__}"
        except Exception as e:
            print(f"Could not set menu name: {e}")

    if sys.platform == "win32":
        try:
            import ctypes
            myappid = "MarkoPolo.Explorer.App.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"Error setting Windows AppUserModelID: {e}")

    app = QApplication(sys.argv)
    app.setApplicationName(f"Marko Polo Explorer v{__version__}")
    
    font = QFont(".AppleSystemUIFont", 11)
    app.setFont(font)
    
    ico_path = os.path.join(script_dir, "markopolo.ico")
    png_path = os.path.join(script_dir, "markopolo.png")
    icon_path = ico_path if (sys.platform == "win32" and os.path.exists(ico_path)) else png_path

    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
        if platform.system() == "Darwin" and HAS_PYOBJC:
            try:
                from AppKit import NSApplication, NSImage
                ns_img = NSImage.alloc().initWithContentsOfFile_(png_path if os.path.exists(png_path) else icon_path)
                if ns_img:
                    NSApplication.sharedApplication().setApplicationIconImage_(ns_img)
            except Exception as e:
                print(f"Error setting macOS Dock icon: {e}")
    
    win = ImageCaptureClone()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
