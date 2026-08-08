#!/usr/bin/env python3
"""
Windows NSIS / SFX Executable Generator & Builder.
Compiles 'WINDOWS/installer.nsi' via makensis if available, or generates a native 64-bit Windows Setup Executable
('Install_MarkoPoloExplorer.exe') directly on macOS.
"""
import os
import sys
import shutil
import subprocess
import urllib.request
import py7zr

def create_windows_exe():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    windows_dir = os.path.join(script_dir, "WINDOWS")
    nsi_path = os.path.join(windows_dir, "installer.nsi")
    out_exe_path = os.path.join(script_dir, "Install_MarkoPoloExplorer.exe")

    print("[*] Building Windows Executable Installer (Install_MarkoPoloExplorer.exe)...")

    # 0. Ensure Python 3.13 64-bit Windows Installer is bundled in WINDOWS/python-installer.exe
    py_installer_path = os.path.join(windows_dir, "python-installer.exe")
    if not os.path.exists(py_installer_path) or os.path.getsize(py_installer_path) < 20000000:
        py_url = "https://www.python.org/ftp/python/3.13.1/python-3.13.1-amd64.exe"
        try:
            print("[*] Downloading official Python 3.13 64-bit Windows installer...")
            req = urllib.request.Request(py_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response, open(py_installer_path, 'wb') as out_file:
                out_file.write(response.read())
            print(f"✅ Downloaded python-installer.exe ({os.path.getsize(py_installer_path)} bytes).")
        except Exception as e:
            print(f"[!] Warning: Could not fetch python-installer.exe: {e}")

    # 1. Try local Inno Setup compiler (iscc) or NSIS (makensis) if installed
    iss_path = os.path.join(windows_dir, "installer.iss")
    iscc_bin = shutil.which("iscc") or shutil.which("ISCC")
    if iscc_bin:
        print(f"[*] Running local Inno Setup compiler: {iscc_bin} {iss_path}")
        res = subprocess.run([iscc_bin, iss_path], cwd=windows_dir)
        win_iss_out = os.path.join(windows_dir, "Install_MarkoPoloExplorer.exe")
        if res.returncode == 0 and os.path.exists(win_iss_out):
            shutil.move(win_iss_out, out_exe_path)
            print(f"✅ SUCCESS! Native Inno Setup Windows Installer compiled:\n    {out_exe_path} ({os.path.getsize(out_exe_path)} bytes)")
            return

    makensis_bin = shutil.which("makensis")
    if makensis_bin:
        print(f"[*] Running local NSIS compiler: {makensis_bin} {nsi_path}")
        res = subprocess.run([makensis_bin, nsi_path], cwd=windows_dir)
        if res.returncode == 0 and os.path.exists(out_exe_path):
            print(f"✅ SUCCESS! Native NSIS Windows Installer compiled:\n    {out_exe_path} ({os.path.getsize(out_exe_path)} bytes)")
            return

    # 2. Local macOS Fallback: Generate 64-bit Windows 7zSFX Setup Executable
    print("[*] Generating 64-bit Windows Setup Executable on macOS...")

    stub_path = os.path.join(script_dir, ".win64_sfx_stub.exe")
    if not os.path.exists(stub_path) or os.path.getsize(stub_path) != 30092:
        url = "https://www.7-zip.org/a/7z2408-x64.exe"
        try:
            print("[*] Downloading official 7-Zip 24.08 universal Windows SFX stub header...")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = response.read()
                sfx_offset = data.find(b'7z\xbc\xaf\x27\x1c')
                if sfx_offset > 0:
                    stub_data = data[:sfx_offset]
                    with open(stub_path, 'wb') as stub_file:
                        stub_file.write(stub_data)
                    print(f"✅ Downloaded official 7-Zip universal SFX stub ({len(stub_data)} bytes).")
        except Exception as e:
            print(f"[!] Warning: Could not fetch 7zSFX stub: {e}")

    # Build 7z Payload Archive from WINDOWS folder using process-unique temp file
    temp_7z = os.path.join(script_dir, f".sfx_payload_{os.getpid()}.7z")
    try:
        if os.path.exists(temp_7z):
            os.remove(temp_7z)

        with py7zr.SevenZipFile(temp_7z, 'w') as archive:
            archive.writeall(windows_dir, arcname='')

        # SFX Setup Directive Config
        config_text = (
            ";!@Install@!utf-8!\n"
            'Title="Marko Polo Explorer Setup"\n'
            'RunProgram="Install Marko Polo Explorer.bat"\n'
            ";!@InstallEnd@!\n"
        ).encode('utf-8')

        if os.path.exists(stub_path):
            with open(out_exe_path, 'wb') as exe_out:
                with open(stub_path, 'rb') as stub_in:
                    exe_out.write(stub_in.read())
                exe_out.write(config_text)
                with open(temp_7z, 'rb') as payload_in:
                    exe_out.write(payload_in.read())
            print(f"✅ SUCCESS! Generated 64-bit Windows Setup Executable:\n    {out_exe_path} ({os.path.getsize(out_exe_path)} bytes)")
    finally:
        if os.path.exists(temp_7z):
            try: os.remove(temp_7z)
            except Exception: pass

if __name__ == "__main__":
    create_windows_exe()
