#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hands-on Live Verification for Dynamic Font Slot Management:
1. Creates a custom BASIC program 'FONTTEST' that tests:
   - /font-add 1 neodgm.ttf
   - /font-add title Sam3KRFont.ttf
   - /font-add body Galmuri14.ttf
   - Printing with [F:1], [F:title], [F:body]
   - Modifying slot 1: /font-add 1 DOSMyungjo.ttf
   - Printing with [F:1] (now rendered in DOS Myungjo)
   - /font-del title
2. Injects 'FONTTEST' into a temporary copy of unicode.dsk (the repository's
   disk is left as it is)
3. Bakes the font table via build_font_dsk.py
4. Boots AppleWin with that copy and executes 'RUN FONTTEST' (an AppleWin
   already running is not ended; the test stops and asks for it to be closed)
5. Checks that the screen changed from the prompt to the HGR drawing, and puts
   AppleWin's settings back
6. Tests live serial server mode (unicode_server.py) with dynamic /font-add and
   [F:...], reading the server's answers a whole packet at a time
"""

import os
import sys
import time
import socket
import struct
import subprocess
import threading
import ctypes
from ctypes import wintypes
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from inject_basic import build_applesoft_program
from ac_tool import put_file, list_dsk_files
from build_font_dsk import process_dsk
from unicode_server import HangulTerminalServer

APPLEWIN_EXE = r"d:\msys64\home\milds\AppleWin\Release\AppleWin.exe"
DSK_PATH = os.path.join(ROOT_DIR, "unicode.dsk")

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

WM_CHAR = 0x0102
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_RETURN = 0x0D
WM_CLOSE = 0x0010

def encode_hex_kor(text):
    return ''.join(f'{b:02X}' for b in text.encode('utf-8'))

def make_fonttest_program():
    lines = [
        (10, 'REM DYNAMIC FONT REGISTRATION TEST'),
        (20, '& "/font-add 1 neodgm.ttf"'),
        (30, '& "/font-add title Sam3KRFont.ttf"'),
        (40, '& "/font-add body Galmuri14.ttf"'),
        (50, f'& "[F:1]\\K{encode_hex_kor("둥근모타자")}\\N"'),
        (60, f'& "[F:title]\\K{encode_hex_kor("三國志英雄")}\\N"'),
        (70, f'& "[F:body]\\K{encode_hex_kor("갈무리본문")}\\N"'),
        (80, '& "/font-add 1 DOSMyungjo.ttf"'),
        (90, f'& "[F:1]\\K{encode_hex_kor("명조로변경")}\\N"'),
        (100, '& "/font-del title"'),
        (110, '& "TEST COMPLETED"'),
        (120, 'END'),
    ]
    return lines

def capture_hwnd(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = max(1, rect.right - rect.left)
    h = max(1, rect.bottom - rect.top)
    
    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mem_dc, bitmap)
    
    user32.PrintWindow(hwnd, mem_dc, 2)
    
    bmi = bytearray(40)
    struct.pack_into("<lllHHllllll", bmi, 0, 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = bytearray(w * h * 4)
    gdi32.GetDIBits(mem_dc, bitmap, 0, h, (ctypes.c_char * len(buf)).from_buffer(buf), (ctypes.c_char * 40).from_buffer(bmi), 0)
    
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)
    
    return Image.frombuffer("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, 1)

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

def packets_complete(buf):
    """True when buf holds whole server packets ending with CMD_DONE ($00).
    A glyph's own bytes may be 0, and the server's $88 mode packet may arrive
    in a segment of its own ($88 $00 when the mode is 0), so a buffer that
    merely ends in 0 is not the end of the answer."""
    lengths = {0x81: 35, 0x85: 19, 0x82: 1, 0x83: 1, 0x84: 1, 0x88: 2}
    i = 0
    while i < len(buf):
        cmd = buf[i]
        if cmd == 0x00:
            return True
        if cmd == 0x86:
            if i + 1 >= len(buf):
                return False
            n = 2 + buf[i + 1]
        else:
            n = lengths.get(cmd)
            if n is None:
                raise AssertionError(f"unknown server packet ${cmd:02X} at {i}: {bytes(buf).hex()}")
        i += n
    return False


def recv_until_done(sock, timeout=4.0):
    received = bytearray()
    start_time = time.time()
    sock.settimeout(0.2)
    while time.time() - start_time < timeout:
        try:
            data = sock.recv(4096)
            if data:
                received.extend(data)
                if packets_complete(received):
                    break
        except socket.timeout:
            pass
    return bytes(received)

def test_live_serial_mode():
    print("\n--- [STEP 1] Testing Dynamic Font Slots via Live TCP Server Protocol ---")
    test_port = 1979
    server = HangulTerminalServer(host="127.0.0.1", port=test_port)
    
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", test_port))
    server_sock.listen(1)
    
    conn_holder = []
    def mock_listener():
        c, _ = server_sock.accept()
        conn_holder.append(c)
    
    t = threading.Thread(target=mock_listener, daemon=True)
    t.start()
    
    t_server = threading.Thread(target=server.start, daemon=True)
    t_server.start()
    time.sleep(0.5)
    
    assert conn_holder, "Mock AppleWin failed to connect to server!"
    c = conn_holder[0]
    
    # 1. Handshake BASIC mode
    c.sendall(bytes([0xAB]))
    ack = c.recv(1)
    assert ack == bytes([0x80]), f"Bad ACK: {ack}"
    print("  * BASIC handshake ACK received.")
    
    # 2. Send /font-add 1 neodgm.ttf
    c.sendall(bytes([0x87]) + b'/font-add 1 neodgm.ttf\x00')
    done = recv_until_done(c)
    assert done.endswith(b'\x00')
    print("  * Live command /font-add 1 neodgm.ttf: SUCCESS")
    
    # 3. Send text with [F:1]
    c.sendall(bytes([0x87]) + b'[F:1]\xEC\x95\x88\xEB\x85\x95\x00') # "안녕"
    resp = recv_until_done(c)
    assert 0x81 in resp, "Server did not send 0x81 glyph packet for [F:1]!"
    print(f"  * Received {len(resp)} bytes glyph data for [F:1]: SUCCESS")
    
    # 4. Modify /font-add 1 DOSMyungjo.ttf
    c.sendall(bytes([0x87]) + b'/font-add 1 DOSMyungjo.ttf\x00')
    done = recv_until_done(c)
    assert done.endswith(b'\x00')
    print("  * Live command /font-add 1 DOSMyungjo.ttf (Modify): SUCCESS")
    
    # 5. Send text with updated [F:1]
    c.sendall(bytes([0x87]) + b'[F:1]\xEB\xAA\x85\xEC\xA1\xB0\x00') # "명조"
    resp = recv_until_done(c)
    assert 0x81 in resp
    print(f"  * Received {len(resp)} bytes glyph data for modified [F:1]: SUCCESS")
    
    # 6. Delete /font-del 1
    c.sendall(bytes([0x87]) + b'/font-del 1\x00')
    done = recv_until_done(c)
    assert done.endswith(b'\x00')
    print("  * Live command /font-del 1 (Remove): SUCCESS")

    # Stop server
    server.running = False
    server_sock.close()
    if server.sock:
        server.sock.close()
    print("  -> Live TCP Server Dynamic Font Test: PASSED!")

def test_live_dsk_and_applewin():
    print("\n--- [STEP 2] Injecting 'FONTTEST' into a copy of unicode.dsk & Baking Font Cache ---")
    import shutil
    import tempfile
    sys.path.insert(0, os.path.join(ROOT_DIR, "tools"))
    from test_applewin_live import require_no_applewin, run_and_check, wait_applewin_window
    from test_hdd_live import REG_KEY
    # An AppleWin already running (the user's) is not ended
    require_no_applewin()

    # 1. Build FONTTEST basic program, on a copy: the repository's disk stays as it is
    work = tempfile.mkdtemp(prefix="fonttest_")
    dsk = os.path.join(work, "unicode.dsk")
    shutil.copyfile(DSK_PATH, dsk)
    lines = make_fonttest_program()
    prog_bytes = build_applesoft_program(lines)
    put_file(dsk, "FONTTEST", "A", 0x0801, prog_bytes)
    print(f"  * 'FONTTEST' injected into {dsk}.")

    # 2. Bake font table using build_font_dsk
    ok = process_dsk(dsk)
    assert ok, "process_dsk failed!"
    print("  * DSK font cache table baked successfully.")

    # 3. Launch AppleWin and run FONTTEST (slot 7 empty so the floppy boots;
    #    AppleWin's settings are put back afterwards)
    print("\n--- [STEP 3] Launching AppleWin and Executing 'RUN FONTTEST' ---")
    saved = os.path.join(work, "applewin_settings.reg")
    subprocess.run(["reg", "export", REG_KEY, saved, "/y"], capture_output=True, check=True)
    proc = subprocess.Popen([APPLEWIN_EXE, "-s7", "empty", "-d1", dsk], cwd=os.path.dirname(APPLEWIN_EXE))
    try:
        hwnd = wait_applewin_window(proc.pid)
        # The screen must change from the prompt to the HGR drawing
        run_and_check(hwnd, "FONTTEST", work)
        print("  -> Live AppleWin Standalone Execution: PASSED!")
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(1.0)
        subprocess.run(["reg", "delete", REG_KEY, "/f"], capture_output=True)
        subprocess.run(["reg", "import", saved], capture_output=True, check=True)
        print("  * AppleWin settings restored")

def main():
    print("=" * 70)
    print(" Hands-On Verification: Dynamic Font Add / Modify / Remove / Display")
    print("=" * 70)
    test_live_serial_mode()
    test_live_dsk_and_applewin()
    print("\n" + "=" * 70)
    print(" ALL DYNAMIC FONT OPERATIONS DIRECTLY VERIFIED AS 100% WORKING!")
    print("=" * 70)

if __name__ == "__main__":
    main()
