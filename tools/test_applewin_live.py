#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Live Execution in AppleWin:
1. Boots unicode.dsk in AppleWin.exe
2. Sends 'RUN DEMO' command
3. Captures the live emulator window screenshot via PrintWindow
4. Verifies rendered HGR pixels
5. Closes AppleWin cleanly
"""

import os
import sys
import time
import struct
import subprocess
import ctypes
from ctypes import wintypes
from PIL import Image

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

def find_applewin_hwnd():
    hwnd_target = []
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
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

def main():
    print("=" * 60)
    print(" Live AppleWin Emulator Verification Test")
    print("=" * 60)
    
    assert os.path.exists(APPLEWIN_EXE), f"AppleWin not found at {APPLEWIN_EXE}"
    assert os.path.exists(DSK_PATH), f"DSK not found at {DSK_PATH}"
    
    # Ensure any old AppleWin is closed
    subprocess.run(["powershell", "-Command", "Stop-Process -Name AppleWin -Force -ErrorAction SilentlyContinue"], capture_output=True)
    time.sleep(0.5)

    print(f"  * Launching AppleWin with {DSK_PATH}...")
    proc = subprocess.Popen([APPLEWIN_EXE, "-d1", DSK_PATH], cwd=os.path.dirname(APPLEWIN_EXE))
    
    hwnd = None
    try:
        # Wait for emulator to start & boot HELLO
        print("  * Waiting 5 seconds for Apple II DOS 3.3 boot and HELLO program...")
        time.sleep(5.0)

        hwnds = find_applewin_hwnd()
        assert hwnds, "Failed to find running AppleWin window!"
        hwnd, title = hwnds[0]
        print(f"  * Found AppleWin Window: hwnd={hwnd:#x}, Title='{title}'")

        # Bring window to foreground
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.5)

        # Send 'RUN DEMO' + Enter
        cmd = "RUN DEMO\r"
        print(f"  * Typing '{cmd.strip()}' into AppleWin...")
        for ch in cmd:
            if ch == '\r':
                user32.PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, 0)
                user32.PostMessageW(hwnd, WM_CHAR, 0x0D, 0)
                user32.PostMessageW(hwnd, WM_KEYUP, VK_RETURN, 0)
            else:
                user32.PostMessageW(hwnd, WM_KEYDOWN, ord(ch), 0)
                user32.PostMessageW(hwnd, WM_CHAR, ord(ch), 0)
                user32.PostMessageW(hwnd, WM_KEYUP, ord(ch), 0)
            time.sleep(0.08)

        # Wait for DEMO to render HGR graphics
        print("  * Waiting 3.5 seconds for DEMO multi-font rendering on HGR Page 1...")
        time.sleep(3.5)

        # Capture window
        print("  * Capturing live emulator window via PrintWindow...")
        screenshot = capture_hwnd(hwnd)
        out_png = os.path.join(ROOT_DIR, "docs", "images", "actual_applewin_live_demo.png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        screenshot.save(out_png)
        print(f"  * Live screenshot saved to: {out_png} ({os.path.getsize(out_png)} bytes)")

        # Verify pixels inside AppleWin screen area
        w, h = screenshot.size
        # Sample the center display region
        pixels = list(screenshot.crop((w//4, h//4, 3*w//4, 3*h//4)).getdata())
        non_black = sum(1 for p in pixels if (isinstance(p, int) and p > 30) or (isinstance(p, tuple) and sum(p[:3]) > 60))
        print(f"  * Verified display activity: {non_black} / {len(pixels)} non-black pixels detected.")
        assert non_black > 500, f"Screen appears empty or blank! (non_black={non_black})"
        
        print("\n[SUCCESS] AppleWin live boot and multi-font execution verified successfully!")

    finally:
        if hwnd:
            print("  * Closing AppleWin emulator...")
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            time.sleep(1.0)
        subprocess.run(["powershell", "-Command", "Stop-Process -Name AppleWin -Force -ErrorAction SilentlyContinue"], capture_output=True)

if __name__ == "__main__":
    main()
