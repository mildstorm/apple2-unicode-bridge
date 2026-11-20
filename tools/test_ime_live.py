#!/usr/bin/env python3
"""Live AppleWin check of the Ctrl+K 2-Bul-Sik input line.

1. Boots unicode.dsk in AppleWin (Slot 2 SSC = TCP 1977) and starts
   unicode_server.py against it.
2. Types  10 & "  then Ctrl+K and 2-Bul-Sik keys on the Apple II keyboard,
   and captures the input line on the mixed HGR screen while it composes.
3. Ends with Return, closes the quote, LISTs and RUNs the line.

Screenshots go to ime_*.png in the temp directory. Run from the repository root:
    python tools/test_ime_live.py
"""
import os
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from test_applewin_live import (APPLEWIN_EXE, DSK_PATH, WM_CHAR, WM_KEYDOWN,  # noqa: E402
                                WM_KEYUP, capture_hwnd, require_no_applewin, user32,
                                wait_applewin_window)

OUT_DIR = tempfile.gettempdir()


def post_char(hwnd, code):
    # Backspace goes as Ctrl+H ($08), the code the Apple II left arrow sends
    vk = {0x0D: 0x0D, 0x1B: 0x1B}.get(code, 0)
    if vk:
        user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    user32.PostMessageW(hwnd, WM_CHAR, code, 0)
    if vk:
        user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)
    # The Apple II keyboard latch holds one key: give the driver time to
    # read it before the next one overwrites it
    time.sleep(0.12)


def type_text(hwnd, text):
    for ch in text:
        post_char(hwnd, ord(ch))


def _grab(hwnd):
    """The window as it is on screen, copied with BitBlt. PrintWindow
    (capture_hwnd) makes AppleWin repaint the whole window, and polled a
    few times a second that flashes the screen."""
    import ctypes
    import struct
    from ctypes import wintypes
    from PIL import Image
    gdi32 = ctypes.windll.gdi32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = max(1, rect.right - rect.left), max(1, rect.bottom - rect.top)
    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mem_dc, bitmap)
    gdi32.BitBlt(mem_dc, 0, 0, w, h, hwnd_dc, 0, 0, 0x00CC0020)   # SRCCOPY
    bmi = bytearray(40)
    struct.pack_into("<lllHHllllll", bmi, 0, 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = bytearray(w * h * 4)
    gdi32.GetDIBits(mem_dc, bitmap, 0, h, (ctypes.c_char * len(buf)).from_buffer(buf),
                    (ctypes.c_char * 40).from_buffer(bmi), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)
    return Image.frombuffer("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, 1)


def _screen(hwnd):
    img = _grab(hwnd).convert("L")
    w, h = img.size
    # The Apple II screen, without the title bar, frame and button bar
    return img.crop((10, 33, w - 56, h - 9)).point(lambda v: 255 if v > 40 else 0)


def wait_ready(hwnd, timeout=45.0, settle=1.5):
    """Waits until the Apple II is idle at a prompt: the screen shows
    something and has not changed for `settle` seconds, apart from the
    blinking cursor (one cell), and the cursor has blinked: a screen that
    is merely still may be a disk loading (with no cursor in sight, as on a
    full HGR screen, five still seconds will do). Keys posted while it is busy
    (booting, loading a file, drawing) are lost but the last: the keyboard
    holds one key, so POKE typed during HELLO's BLOAD arrives as E and
    BASIC answers ?SYNTAX ERROR."""
    from PIL import ImageChops
    cursor_cell = 28 * 32 + 200
    start = time.time()
    last = None
    still_since = None
    blinked = False
    while time.time() - start < timeout:
        cur = _screen(hwnd)
        if last is not None:
            changed = ImageChops.difference(cur, last).histogram()[255]
            if changed <= cursor_cell:
                still_since = still_since or time.time()
                blinked = blinked or changed > 0
                # A full HGR screen shows no cursor: then a longer stillness
                quiet = time.time() - still_since
                if (blinked and quiet >= settle) or quiet >= settle + 3.5:
                    return
            else:
                still_since = None
                blinked = False
        last = cur
        time.sleep(0.25)
    raise TimeoutError("the Apple II did not come back to a prompt")


def type_command(hwnd, text):
    """A BASIC command or line, typed once the Apple II is idle."""
    wait_ready(hwnd)
    type_text(hwnd, text)


def shot(hwnd, name):
    path = os.path.join(OUT_DIR, f"ime_{name}.png")
    capture_hwnd(hwnd).save(path)
    print(f"  * {path}")
    return path


def main():
    require_no_applewin()
    # Slot 7 empty, so a hard disk left there (AppleWin keeps slot settings
    # given on its command line) does not boot instead of the floppy; the
    # settings are put back afterwards
    from test_hdd_live import REG_KEY
    saved = os.path.join(tempfile.gettempdir(), "applewin_settings_ime.reg")
    subprocess.run(["reg", "export", REG_KEY, saved, "/y"], capture_output=True, check=True)
    aw = subprocess.Popen([APPLEWIN_EXE, "-s7", "empty", "-d1", DSK_PATH],
                          cwd=os.path.dirname(APPLEWIN_EXE))
    log_path = os.path.join(tempfile.gettempdir(), "ime_live_server.log")
    print(f"  * server log: {log_path}")
    log = open(log_path, "w", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    srv = subprocess.Popen([sys.executable, os.path.join(ROOT_DIR, "unicode_server.py")],
                           stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                           cwd=ROOT_DIR, env=env)
    try:
        time.sleep(3.0)
        hwnd = wait_applewin_window(aw.pid)

        type_command(hwnd, "POKE 24576,0\r")   # the cache off: & goes to the server
        type_command(hwnd, '10 & "')
        post_char(hwnd, 0x0B)                    # Ctrl+K
        time.sleep(1.0)
        type_text(hwnd, "dkssudgktpdy dovmf2 rhk")  # 안녕하세요 애플2 과
        time.sleep(1.0)
        shot(hwnd, "composing")                   # 과 still composing, inverse
        post_char(hwnd, 0x08)                    # Backspace: 과 -> 고
        time.sleep(0.6)
        shot(hwnd, "backspace")
        post_char(hwnd, 0x0B)                    # 한 -> A
        time.sleep(0.6)
        type_text(hwnd, " ok")
        time.sleep(0.8)
        shot(hwnd, "english")
        post_char(hwnd, 0x0D)                    # Return: into the BASIC line
        time.sleep(1.0)
        shot(hwnd, "injected")
        type_command(hwnd, '"\r')
        time.sleep(0.5)
        type_command(hwnd, "LIST\r")
        time.sleep(1.0)
        shot(hwnd, "list")
        type_command(hwnd, "RUN\r")
        time.sleep(3.0)
        shot(hwnd, "run")

        # A line longer than the 19 cells pages along; ESC then cancels it
        type_command(hwnd, '20 & "')
        post_char(hwnd, 0x0B)
        time.sleep(1.0)
        post_char(hwnd, 0x0B)                    # back to 한 (the mode is kept)
        time.sleep(0.4)
        type_text(hwnd, "rkskekfkakqktkdkwkckzkxkvkgk" * 1)  # 가나다라마바사아자차카타파하
        type_text(hwnd, "rkskekfkakqktkdk")                   # 가나다라마바사아
        time.sleep(1.5)
        shot(hwnd, "paging")
        post_char(hwnd, 0x1B)
        time.sleep(1.0)
        type_command(hwnd, 'X"\r')
        time.sleep(0.5)
        type_command(hwnd, "LIST 20\r")
        time.sleep(1.0)
        shot(hwnd, "cancel")

        # Hanja candidates, then kana, Russian and Greek on one line
        type_command(hwnd, '30 & "')
        post_char(hwnd, 0x0B)
        time.sleep(1.0)
        type_text(hwnd, "gks")
        post_char(hwnd, 0x0A)                    # Ctrl+J: Hanja for 한
        time.sleep(1.5)
        shot(hwnd, "hanja")
        post_char(hwnd, 0x1B)                    # Esc closes the list only
        time.sleep(0.8)
        post_char(hwnd, 0x0A)
        time.sleep(0.8)
        post_char(hwnd, 0x1B)                    # a second Esc, still only the list
        time.sleep(0.8)
        post_char(hwnd, 0x0A)
        time.sleep(0.8)
        type_text(hwnd, "1 ")                    # 限
        post_char(hwnd, 0x0C)                    # あ
        type_text(hwnd, "nihon ")
        post_char(hwnd, 0x0C)                    # ア
        post_char(hwnd, 0x0C)                    # Я
        type_text(hwnd, "ghbdtn ")
        post_char(hwnd, 0x0C)                    # Ω
        type_text(hwnd, "kalhm;era")
        time.sleep(1.5)
        shot(hwnd, "multi")
        post_char(hwnd, 0x0D)
        time.sleep(1.0)
        type_command(hwnd, '"\r')
        time.sleep(0.5)
        type_command(hwnd, "RUN\r")
        time.sleep(4.0)
        shot(hwnd, "multi_run")
        wait_ready(hwnd)
        log.flush()
        drawn = [l for l in open(log_path, encoding="utf-8") if "BASIC &" in l]
        # POKE 24576,0 took: the RUNs went to the server, not the $6000 cache
        assert len(drawn) >= 3, f"the server drew {len(drawn)} & strings, not 3 (did a command lose its keys?)"
        print("[done] check the screenshots and the server log")
    finally:
        srv.terminate()
        aw.terminate()
        aw.wait(10)
        log.close()
        time.sleep(1.0)
        subprocess.run(["reg", "delete", REG_KEY, "/f"], capture_output=True)
        subprocess.run(["reg", "import", saved], capture_output=True, check=True)
        print("  * AppleWin settings restored")


if __name__ == "__main__":
    main()
