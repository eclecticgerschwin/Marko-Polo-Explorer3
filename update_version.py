#!/usr/bin/env python3
"""
Automatic Version Generator & Sync Tool for Marko Polo Explorer.
Generates date-coded version with 24h hour (e.g. DDMMYYHH -> '29072622') and updates:
  - version.json
  - image_capture_app.py
  - MAC/image_capture_app.py
  - WINDOWS/image_capture_app.py
"""
import os
import json
import re
from datetime import datetime

def bump_version():
    now = datetime.now()
    date_version = now.strftime("%d%m%y%H") # e.g. '29072622'
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    v_json_path = os.path.join(script_dir, "version.json")
    
    # 1. Update version.json
    v_data = {
        "version": date_version,
        "release_notes": f"Marko Polo Explorer v{date_version} release.",
        "mac": {
            "url": "http://marko.com.hr/markopolo/MarkoPoloExplorer.dmg"
        },
        "windows": {
            "url": "http://marko.com.hr/markopolo/MarkoPoloExplorer.zip"
        }
    }
    
    with open(v_json_path, "w", encoding="utf-8") as f:
        json.dump(v_data, f, indent=2)
    print(f"Updated version.json -> version: {date_version}")
    
    # 2. Update __version__ in image_capture_app.py
    py_paths = [
        os.path.join(script_dir, "image_capture_app.py"),
        os.path.join(script_dir, "MAC", "image_capture_app.py"),
        os.path.join(script_dir, "WINDOWS", "image_capture_app.py"),
    ]
    
    pattern = re.compile(r'__version__\s*=\s*"[^"]*"')
    new_line = f'__version__ = "{date_version}"'
    
    for p in py_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            updated_content = pattern.sub(new_line, content)
            with open(p, "w", encoding="utf-8") as f:
                f.write(updated_content)
            print(f"Updated {p} -> {new_line}")

    # 3. Sync files across MAC and WINDOWS release folders
    import shutil
    for folder in ("MAC", "WINDOWS"):
        target_dir = os.path.join(script_dir, folder)
        if os.path.exists(target_dir):
            shutil.copy2(v_json_path, os.path.join(target_dir, "version.json"))
            updater_src = os.path.join(script_dir, "updater.py")
            if os.path.exists(updater_src):
                shutil.copy2(updater_src, os.path.join(target_dir, "updater.py"))

    print(f"\nSuccessfully set version code to: {date_version}")

if __name__ == "__main__":
    bump_version()
