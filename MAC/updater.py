#!/usr/bin/env python3
"""
Marko Polo Explorer - Detached Auto-Updater Script
Waits for main app PID to terminate, extracts downloaded update ZIP over target directory,
and relaunches application cleanly.

Handles ZIP structures with a program/ subfolder (installer ZIPs) by extracting
only the program/ contents into the target directory, skipping installer-only files.
"""
import sys
import os
import time
import zipfile
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description="Marko Polo Explorer Auto-Updater")
    parser.add_argument("--zip", required=True, help="Path to downloaded update ZIP file")
    parser.add_argument("--target", required=True, help="Target directory to extract files into")
    parser.add_argument("--pid", type=int, default=0, help="PID of main application process to wait for")
    parser.add_argument("--launch", default="", help="Command line to execute for app restart")
    args = parser.parse_args()

    print(f"[Updater] Target folder: {args.target}")
    print(f"[Updater] Waiting for process PID {args.pid} to close...")

    # Wait for the main app process to fully terminate (up to 10s)
    if args.pid > 0:
        time.sleep(0.8)
        for _ in range(20):
            try:
                if sys.platform == "win32":
                    import ctypes
                    SYNCHRONIZE = 0x00100000
                    handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, args.pid)
                    if handle:
                        ctypes.windll.kernel32.CloseHandle(handle)
                        time.sleep(0.4)
                    else:
                        break
                else:
                    os.kill(args.pid, 0)
                    time.sleep(0.4)
            except (OSError, Exception):
                break

    time.sleep(0.5)

    # Extract update zip over target folder
    if os.path.exists(args.zip) and os.path.exists(args.target):
        try:
            print(f"[Updater] Extracting {args.zip} into {args.target}...")

            with zipfile.ZipFile(args.zip, 'r') as zip_ref:
                # Check if ZIP has a program/ subfolder structure (installer ZIP)
                # If so, only extract files from program/ and remap paths
                all_names = zip_ref.namelist()
                has_program_subfolder = any(n.startswith("program/") for n in all_names)

                if has_program_subfolder:
                    print("[Updater] Detected program/ subfolder in ZIP — extracting program contents only...")
                    for member in zip_ref.infolist():
                        # Skip the installer batch file and the program/ directory entry itself
                        if not member.filename.startswith("program/"):
                            continue
                        if member.filename == "program/" or member.filename == "program":
                            continue

                        # Strip the "program/" prefix to extract into target root
                        relative_path = member.filename[len("program/"):]
                        if not relative_path:
                            continue

                        target_path = os.path.join(args.target, relative_path)

                        # Create parent directories if needed
                        if member.is_dir():
                            os.makedirs(target_path, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with zip_ref.open(member) as src, open(target_path, 'wb') as dst:
                                dst.write(src.read())
                            print(f"  [OK] {relative_path}")
                else:
                    # Flat ZIP structure — extract everything directly
                    zip_ref.extractall(args.target)

            print("[Updater] Update extraction successful!")
        except Exception as e:
            print(f"[Updater] Extraction error: {e}")
        finally:
            try:
                os.remove(args.zip)
            except Exception:
                pass

    # Relaunch application
    if args.launch:
        print(f"[Updater] Relaunching app with: {args.launch}")
        try:
            subprocess.Popen(args.launch, shell=True, cwd=args.target)
        except Exception as e:
            print(f"[Updater] Failed to relaunch app: {e}")

if __name__ == "__main__":
    main()
