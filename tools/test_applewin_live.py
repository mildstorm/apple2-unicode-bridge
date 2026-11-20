#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Live Execution in AppleWin:
1. Boots unicode.dsk in AppleWin.exe (slot 7 empty, so a hard disk left in
   AppleWin's settings does not boot instead)
2. Types 'RUN DEMO', then 'RUN COLORDEMO', each once the Apple II is idle
3. Checks that each one changed the screen from the text prompt to HGR
   drawing (most of the screen differs), not merely that it is not blank
4. Saves the screenshots as live_*.png in the temp directory (--out-dir)
5. Closes the AppleWin it started and puts AppleWin's settings back

An AppleWin that is already running is left alone: the test stops and asks
for it to be closed rather than ending it.

    python tools/test_applewin_live.py [--out-dir DIR]
"""

import os
import sys
import time
import struct
import subprocess
import tempfile
import ctypes
from ctypes import wintypes
from PIL import Image, ImageChops

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
APPLEWIN_EXE = r"d:\msys64\home\milds\AppleWin\Release\AppleWin.exe"
DSK_PATH = os.path.join(ROOT_DIR, "unicode.dsk")

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

WM_CHAR = 0x0102
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_RETURN = 0x0D
WM_CLOSE = 0x0010

def find_applewin_hwnd(pid=None):
    """Visible windows of AppleWin: those of process `pid` when given (the
    one a test started), else any whose title says Apple."""
    hwnd_target = []
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            if pid is not None:
                owner = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
                if owner.value != pid:
                    return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if "Apple" in title or "AppleWin" in title:
                    hwnd_target.append((hwnd, title))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return hwnd_target


def wait_applewin_window(pid, timeout=15.0):
    """The main window of the AppleWin process `pid`, once it is up."""
    start = time.time()
    while time.time() - start < timeout:
        hwnds = find_applewin_hwnd(pid)
        if hwnds:
            return hwnds[0][0]
        time.sleep(0.3)
    raise AssertionError("AppleWin window not found")


def require_no_applewin():
    """Live tests drive an AppleWin of their own. One already running (the
    user's) is not ended: stop here instead."""
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq AppleWin.exe", "/NH"],
                         capture_output=True, text=True).stdout
    if "AppleWin.exe" in out:
        raise SystemExit("AppleWin is already running. Close it first; this test starts its own.")

def capture_hwnd(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = max(1, rect.right - rect.left)
    h = max(1, rect.bottom - rect.top)
    
    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mem_dc, bitmap)
    
    # PW_RENDERFULLCONTENT = 2
    user32.PrintWindow(hwnd, mem_dc, 2)
    
    bmi = bytearray(40)
    struct.pack_into("<lllHHllllll", bmi, 0, 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = bytearray(w * h * 4)
    gdi32.GetDIBits(mem_dc, bitmap, 0, h, (ctypes.c_char * len(buf)).from_buffer(buf), (ctypes.c_char * 40).from_buffer(bmi), 0)
    
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)
    
    img = Image.frombuffer("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, 1)
    return img

def run_and_check(hwnd, program, out_dir):
    """Types RUN <program> at the idle prompt and checks that the screen
    then differs from the prompt over a large part of it: the program
    switched to HGR and drew. The boot text alone (the old check, any 500
    lit pixels) passes even when the command never arrived."""
    from test_ime_live import _screen, type_command, wait_ready
    wait_ready(hwnd)
    before = _screen(hwnd)
    type_command(hwnd, f"RUN {program}\r")
    wait_ready(hwnd)
    after = _screen(hwnd)
    shot = capture_hwnd(hwnd)
    out_png = os.path.join(out_dir, f"live_{program.lower()}.png")
    shot.save(out_png)
    changed = ImageChops.difference(before, after).histogram()[255]
    lit = after.histogram()[255]
    print(f"  * {program}: {changed} pixels changed, {lit} lit -> {out_png}")
    assert changed > 2000 and lit > 2000, (
        f"RUN {program} did not draw (changed={changed}, lit={lit}); see {out_png}")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Boots unicode.dsk in AppleWin and runs DEMO and COLORDEMO")
    ap.add_argument("--out-dir", default=tempfile.gettempdir(),
                    help="where the screenshots go (default: the temp directory)")
    args = ap.parse_args(sys.argv[1:] if __name__ == "__main__" else [])

    print("=" * 60)
    print(" Live AppleWin Emulator Verification Test")
    print("=" * 60)

    assert os.path.exists(APPLEWIN_EXE), f"AppleWin not found at {APPLEWIN_EXE}"
    assert os.path.exists(DSK_PATH), f"DSK not found at {DSK_PATH}"
    require_no_applewin()

    sys.path.insert(0, SCRIPT_DIR)
    from test_hdd_live import REG_KEY
    saved = os.path.join(tempfile.gettempdir(), "applewin_settings_live.reg")
    subprocess.run(["reg", "export", REG_KEY, saved, "/y"], capture_output=True, check=True)

    print(f"  * Launching AppleWin with {DSK_PATH}...")
    proc = subprocess.Popen([APPLEWIN_EXE, "-s7", "empty", "-d1", DSK_PATH],
                            cwd=os.path.dirname(APPLEWIN_EXE))
    try:
        hwnd = wait_applewin_window(proc.pid)
        run_and_check(hwnd, "DEMO", args.out_dir)
        run_and_check(hwnd, "COLORDEMO", args.out_dir)
        print("\n[SUCCESS] AppleWin live boot, multi-font DEMO, and COLORDEMO execution verified successfully!")
    finally:
        print("  * Closing the AppleWin this test started...")
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(1.0)
        subprocess.run(["reg", "delete", REG_KEY, "/f"], capture_output=True)
        subprocess.run(["reg", "import", saved], capture_output=True, check=True)
        print("  * AppleWin settings restored")

if __name__ == "__main__":
    main()
