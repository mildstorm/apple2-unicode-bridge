#!/usr/bin/env python3
"""Live AppleWin check of drawing from the ProDOS hard-disk font, no server.

Boots build/unicode_hdd.hdv (python build_hdd.py) from a hard-disk card in
slot 7, then runs HDDEMO and JEMANG and captures the screen after each.
Screenshots go to hdd_*.png in the temp directory. AppleWin saves the slot 7
card and image given on its command line to its settings; they are put back
as they were afterwards.

    python tools/test_hdd_live.py [image.hdv]
"""
import os
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from test_applewin_live import APPLEWIN_EXE, capture_hwnd, find_applewin_hwnd  # noqa: E402
from test_ime_live import type_text  # noqa: E402

REG_KEY = r"HKCU\Software\AppleWin"


def shot(hwnd, name):
    path = os.path.join(tempfile.gettempdir(), f"hdd_{name}.png")
    capture_hwnd(hwnd).save(path)
    print(f"  * {path}")


def run_demos():
    hwnds = find_applewin_hwnd()
    assert hwnds, "AppleWin window not found"
    hwnd = hwnds[0][0]
    shot(hwnd, "startup")
    type_text(hwnd, "RUN HDDEMO\r")
    time.sleep(4.0)
    shot(hwnd, "demo")
    type_text(hwnd, "RUN JEMANG\r")
    time.sleep(4.0)
    shot(hwnd, "jemang")


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT_DIR, "build", "unicode_hdd.hdv")
    subprocess.run(["powershell", "-Command",
                    "Stop-Process -Name AppleWin -Force -ErrorAction SilentlyContinue"],
                   capture_output=True)
    time.sleep(0.5)
    saved = os.path.join(tempfile.gettempdir(), "applewin_settings.reg")
    subprocess.run(["reg", "export", REG_KEY, saved, "/y"], capture_output=True, check=True)
    aw = subprocess.Popen([APPLEWIN_EXE, "-s7", "hdc", "-h1", os.path.abspath(image)],
                          cwd=os.path.dirname(APPLEWIN_EXE))
    try:
        time.sleep(7.0)
        run_demos()
    finally:
        aw.terminate()
        aw.wait(10)
        time.sleep(1.0)
        subprocess.run(["reg", "delete", REG_KEY, "/f"], capture_output=True)
        subprocess.run(["reg", "import", saved], capture_output=True, check=True)
        print("  * AppleWin settings restored")


if __name__ == "__main__":
    main()
